"""Run the full evaluation and write results/eval.md.

    python -m finaudit.evaluate

Costs roughly 100 API calls on the default models (well under $1).
"""

from __future__ import annotations

import json
from collections import Counter

import pandas as pd

from . import bias
from .config import ANSWER_MODEL, DATA_DIR, JUDGE_MODEL, LARGE_CAP, RESULTS_DIR, SMALL_CAP
from .llm import AnthropicClient, LLMClient
from .pipeline import FinAudit
from .questions import BIAS_METRICS, IN_DOC, MANUAL_TRUTH, OUT_OF_DOC
from .verify import numeric_verdict

JUDGE_SAYS_OK = {"GROUNDED"}


def load_truth(ticker: str) -> dict:
    truth = json.loads((DATA_DIR / ticker / "ground_truth.json").read_text())
    truth.update(MANUAL_TRUTH.get(ticker, {}))
    return truth


def run_test_set(fa: FinAudit, truth: dict, metrics=None) -> list[dict]:
    rows = []
    company = fa.filing["company"]
    for template, metric in IN_DOC:
        if metrics and metric not in metrics:
            continue
        tv = truth.get(metric, {}).get("value")
        if tv is None:
            continue
        res = fa.ask(template.format(company=company))
        first, final = res.attempts[0], res.final
        rows.append({"ticker": fa.ticker, "type": "in_doc", "metric": metric,
                     "first_numeric": numeric_verdict(first.answer, tv),
                     "final_numeric": numeric_verdict(final.answer, tv),
                     "first_judge": first.verdict, "final_judge": final.verdict,
                     "retried": len(res.attempts) > 1, "pages": res.pages_used,
                     "answer": final.answer})
    if metrics is None:
        for template in OUT_OF_DOC:
            res = fa.ask(template.format(company=company))
            first, final = res.attempts[0], res.final
            rows.append({"ticker": fa.ticker, "type": "out_of_doc",
                         "metric": template.format(company=company)[:45],
                         "first_numeric": numeric_verdict(first.answer, None),
                         "final_numeric": numeric_verdict(final.answer, None),
                         "first_judge": first.verdict, "final_judge": final.verdict,
                         "retried": len(res.attempts) > 1, "pages": res.pages_used,
                         "answer": final.answer})
    return rows


def judge_agreement(rows: list[dict]) -> pd.DataFrame:
    """Is the judge right? Truth: in-doc answers are right iff the number matches XBRL;
    out-of-doc answers are right iff the model refused."""
    out = []
    for r in rows:
        if r["type"] == "in_doc":
            truly_ok = r["first_numeric"] == "CORRECT"
            judge_ok = r["first_judge"] in JUDGE_SAYS_OK
        else:
            truly_ok = r["first_numeric"] == "REFUSED"
            # accepting an appropriate refusal is the judge saying REFUSED or GROUNDED
            judge_ok = r["first_judge"] in {"REFUSED", "GROUNDED"}
        out.append({"truth": "correct" if truly_ok else "wrong",
                    "judge": "accepted" if judge_ok else "flagged"})
    return pd.crosstab(pd.DataFrame(out).truth, pd.DataFrame(out).judge)


def main(client: LLMClient | None = None) -> None:
    client = client or AnthropicClient()
    RESULTS_DIR.mkdir(exist_ok=True)

    # ---- 1. Main test set on the large-cap filing ---------------------- #
    aapl = FinAudit(LARGE_CAP.ticker, client)
    rows = run_test_set(aapl, load_truth(LARGE_CAP.ticker))
    df = pd.DataFrame(rows)
    in_doc, ood = df[df.type == "in_doc"], df[df.type == "out_of_doc"]

    # ---- 2. Representation-bias probe ---------------------------------- #
    bias_rows, open_rows = [], []
    for comp in (LARGE_CAP, SMALL_CAP):
        fa = aapl if comp is LARGE_CAP else FinAudit(comp.ticker, client)
        truth = load_truth(comp.ticker)
        bias_rows += bias.closed_book(client, fa.filing, truth)
        open_rows += run_test_set(fa, truth, metrics=set(BIAS_METRICS))
    closed = {t: bias.summarize([r for r in bias_rows if r["ticker"] == t])
              for t in (LARGE_CAP.ticker, SMALL_CAP.ticker)}
    open_acc = {t: sum(r["final_numeric"] == "CORRECT" for r in open_rows if r["ticker"] == t)
                for t in (LARGE_CAP.ticker, SMALL_CAP.ticker)}

    # ---- Write report ---------------------------------------------------- #
    agree = judge_agreement(rows)
    md = [f"# FinAudit evaluation\n\nAnswer model: `{ANSWER_MODEL}` · "
          f"judge model: `{JUDGE_MODEL}` · filing: {aapl.filing['company']} 10-K, "
          f"fiscal year ended {aapl.filing['period_end']}\n",
          "## 1. Accuracy against ground truth\n",
          "| | First attempt | After reflection retry |", "|---|---|---|",
          f"| In-document answers with the correct number | "
          f"{(in_doc.first_numeric == 'CORRECT').sum()}/{len(in_doc)} | "
          f"{(in_doc.final_numeric == 'CORRECT').sum()}/{len(in_doc)} |",
          f"| Out-of-document questions correctly refused | "
          f"{(ood.first_numeric == 'REFUSED').sum()}/{len(ood)} | "
          f"{(ood.final_numeric == 'REFUSED').sum()}/{len(ood)} |",
          f"\nRetries triggered: {int(df.retried.sum())} of {len(df)} questions.\n",
          "## 2. Is the judge right? (first attempts vs. ground truth)\n",
          agree.to_markdown(), "",
          "## 3. Representation-bias probe\n",
          "| | " + " | ".join(closed) + " |", "|---|---|---|",
          "| Closed book: answered instead of saying \"I don't know\" | " +
          " | ".join(f"{c['answered']}/{c['questions']}" for c in closed.values()) + " |",
          "| Closed book: answered but wrong (confidently wrong) | " +
          " | ".join(f"{c['confidently_wrong']}/{c['questions']}" for c in closed.values()) + " |",
          "| Open book (same context size): correct number | " +
          " | ".join(f"{open_acc[t]}/{len(BIAS_METRICS)}" for t in open_acc) + " |", "",
          "## Detail\n", df.drop(columns=["answer"]).to_markdown(index=False), "",
          "Verdict counts (final): " + json.dumps(Counter(df.final_judge))]
    (RESULTS_DIR / "eval.md").write_text("\n".join(md))
    pd.DataFrame(rows + open_rows).to_csv(RESULTS_DIR / "eval_rows.csv", index=False)
    pd.DataFrame(bias_rows).to_csv(RESULTS_DIR / "bias_closed_book.csv", index=False)
    print("\n".join(md[:20]))


if __name__ == "__main__":
    main()
