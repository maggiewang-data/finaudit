"""The core loop: retrieve -> answer -> judge -> (retry once if needed) -> log.

Ask one question from the command line:
    python -m finaudit.pipeline AAPL "How much did Apple spend on research and development?"
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import audit, prompts
from .config import (
    ANSWER_MODEL,
    AUDIT_LOG,
    COMPANIES,
    DATA_DIR,
    JUDGE_MODEL,
    MAX_CONTEXT_CHARS,
    MAX_RETRIES,
    TOP_K,
)
from .document import Page, load_pages
from .llm import AnthropicClient, LLMClient
from .retrieval import BM25Retriever
from .verify import Judgement, parse_judgement

# UNPARSEABLE is deliberately not retried: an unreadable judge reply says nothing
# about the answer, so re-asking the answer model would waste a call.
NEEDS_RETRY = {"HALLUCINATED", "PARTIAL"}

# Generous limits. The first live run used 150 tokens for the judge and 600 for
# answers, and replies were cut off mid-sentence ("VERDICT: GRO"). Newer models
# can spend part of the budget before writing visible text, so leave headroom
# and record whenever a reply still hits the limit.
ANSWER_MAX_TOKENS = 1500
JUDGE_MAX_TOKENS = 1000


@dataclass
class Attempt:
    answer: str
    verdict: str
    reason: str
    tokens: int
    judge_raw: str = ""
    truncated: bool = False   # answer or judge reply hit the token limit


@dataclass
class Result:
    ticker: str
    question: str
    pages_used: list[int]
    attempts: list[Attempt] = field(default_factory=list)

    @property
    def final(self) -> Attempt:
        return self.attempts[-1]


def format_context(pages: list[Page], max_chars: int = MAX_CONTEXT_CHARS) -> str:
    return "\n\n".join(f"[p. {p.number}]\n{p.text[:max_chars]}" for p in pages)


class FinAudit:
    def __init__(self, ticker: str, client: LLMClient, pages: list[Page] | None = None,
                 filing: dict | None = None, log_path: Path = AUDIT_LOG):
        folder = DATA_DIR / ticker
        self.ticker = ticker
        self.filing = filing or json.loads((folder / "filing.json").read_text())
        self.pages = pages if pages is not None else load_pages(folder / "10k.htm")
        self.retriever = BM25Retriever(self.pages)
        self.client = client
        self.log_path = log_path

    def _judge(self, context: str, question: str, answer: str) -> tuple[Judgement, int, str]:
        r = self.client.complete(prompts.JUDGE_SYSTEM,
                                 prompts.JUDGE_USER.format(context=context, question=question,
                                                           answer=answer),
                                 model=JUDGE_MODEL, max_tokens=JUDGE_MAX_TOKENS)
        self._judge_cut = r.stop_reason == "max_tokens"
        return parse_judgement(r.text), r.input_tokens + r.output_tokens, r.text

    def ask(self, question: str) -> Result:
        pages = self.retriever.top_k(question, TOP_K)
        context = format_context(pages)
        user = prompts.ANSWER_USER.format(company=self.filing["company"],
                                          period_end=self.filing["period_end"],
                                          context=context, question=question)
        result = Result(self.ticker, question, [p.number for p in pages])

        r = self.client.complete(prompts.ANSWER_SYSTEM, user, model=ANSWER_MODEL,
                                 max_tokens=ANSWER_MAX_TOKENS)
        j, jt, raw = self._judge(context, question, r.text)
        result.attempts.append(Attempt(r.text, j.verdict, j.reason,
                                       r.input_tokens + r.output_tokens + jt, raw,
                                       r.stop_reason == "max_tokens" or self._judge_cut))

        # Reflection: if the judge rejects the answer, show the model why and let it try once more.
        for _ in range(MAX_RETRIES):
            if result.final.verdict not in NEEDS_RETRY:
                break
            retry = user + "\n\n" + prompts.RETRY_USER.format(
                answer=result.final.answer, reason=result.final.reason,
                not_found=prompts.NOT_FOUND)
            r = self.client.complete(prompts.ANSWER_SYSTEM, retry, model=ANSWER_MODEL,
                                     max_tokens=ANSWER_MAX_TOKENS)
            j, jt, raw = self._judge(context, question, r.text)
            result.attempts.append(Attempt(r.text, j.verdict, j.reason,
                                           r.input_tokens + r.output_tokens + jt, raw,
                                           r.stop_reason == "max_tokens" or self._judge_cut))

        audit.write({
            "ticker": self.ticker,
            "accession": self.filing.get("accession"),
            "question": question,
            "pages_used": result.pages_used,
            "answer_model": ANSWER_MODEL,
            "judge_model": JUDGE_MODEL,
            "final_answer": result.final.answer,
            "final_verdict": result.final.verdict,
            "final_reason": result.final.reason,
            "retried": len(result.attempts) > 1,
            "any_truncated": any(a.truncated for a in result.attempts),
            "attempts": [asdict(a) for a in result.attempts],
            "total_tokens": sum(a.tokens for a in result.attempts),
        }, self.log_path)
        return result


if __name__ == "__main__":
    ticker, question = sys.argv[1].upper(), " ".join(sys.argv[2:])
    if ticker not in COMPANIES:
        sys.exit(f"Unknown ticker {ticker}; choose from {list(COMPANIES)}")
    res = FinAudit(ticker, AnthropicClient()).ask(question)
    for i, a in enumerate(res.attempts, 1):
        print(f"--- attempt {i}: {a.verdict} ({a.reason})\n{a.answer}\n")
        if a.verdict == "UNPARSEABLE":
            print(f"[raw judge reply]\n{a.judge_raw}\n")
    print(f"Pages used: {res.pages_used}.  Logged to {AUDIT_LOG}")
