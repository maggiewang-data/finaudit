"""Representation-bias probe: does the model treat a famous company differently
from an obscure one when asked the same questions?

Two conditions, same seven questions for each company:

Closed book (no filing shown). A model that has read a lot about Apple during
training may answer confidently from memory, even when the fiscal year asked
about is newer than anything it saw. For a small company it is more likely to
admit it doesn't know. Confidence that isn't backed by accuracy is the risk.

Open book (filing excerpts shown, same number of pages and characters for both
companies). With the source in front of it, accuracy should no longer depend
on how famous the company is. A remaining gap would point to bias in how the
model reads the text, not just in what it memorized.
"""

from __future__ import annotations

from . import prompts
from .config import ANSWER_MODEL
from .llm import LLMClient
from .questions import BIAS_METRICS, IN_DOC
from .verify import is_refusal, numeric_verdict

TEMPLATES = dict((m, q) for q, m in IN_DOC)


def closed_book(client: LLMClient, filing: dict, truth: dict) -> list[dict]:
    rows = []
    for metric in BIAS_METRICS:
        q = TEMPLATES[metric].format(company=filing["company"])
        r = client.complete(prompts.CLOSED_BOOK_SYSTEM,
                            prompts.CLOSED_BOOK_USER.format(company=filing["company"],
                                                            ticker=filing["ticker"],
                                                            period_end=filing["period_end"],
                                                            question=q),
                            model=ANSWER_MODEL, max_tokens=600)
        tv = truth.get(metric, {}).get("value")
        rows.append({"ticker": filing["ticker"], "condition": "closed_book", "metric": metric,
                     "answer": r.text, "answered": not is_refusal(r.text),
                     "numeric": numeric_verdict(r.text, tv)})
    return rows


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    answered = [r for r in rows if r["answered"]]
    correct = [r for r in answered if r["numeric"] == "CORRECT"]
    return {"questions": n,
            "answered": len(answered),
            "answer_rate": len(answered) / n if n else 0.0,
            "correct": len(correct),
            "confidently_wrong": len(answered) - len(correct),
            "accuracy_when_answered": len(correct) / len(answered) if answered else None}
