"""Download a company's latest 10-K and the matching XBRL facts from SEC EDGAR.

The 10-K is what the model reads. The XBRL facts are the company's own
machine-readable numbers from the same filing, which makes them the ground
truth used to check the model's answers.

Run:  python -m finaudit.sec AAPL UEIC
Needs SEC_USER_AGENT in .env, e.g.  SEC_USER_AGENT="Jane Doe jane@example.com"
"""

from __future__ import annotations

import json
import sys
import time

import requests

from .config import COMPANIES, DATA_DIR, SEC_USER_AGENT, Company

# XBRL concept -> plain-English metric name used throughout the project
METRICS = {
    "RevenueFromContractWithCustomerExcludingAssessedTax": "total_net_sales",
    "ResearchAndDevelopmentExpense": "research_and_development",
    "NetIncomeLoss": "net_income",
    "GrossProfit": "gross_margin",
    "OperatingIncomeLoss": "operating_income",
    "EarningsPerShareDiluted": "diluted_eps",
    "CashAndCashEquivalentsAtCarryingValue": "cash_and_equivalents",
    "PaymentsForRepurchaseOfCommonStock": "share_repurchases",
    "PaymentsOfDividends": "dividends_paid",
    "IncomeTaxExpenseBenefit": "income_tax_provision",
}


def _get(url: str) -> requests.Response:
    if not SEC_USER_AGENT:
        raise RuntimeError("Set SEC_USER_AGENT in .env (SEC requires a name and email).")
    r = requests.get(url, headers={"User-Agent": SEC_USER_AGENT}, timeout=60)
    r.raise_for_status()
    time.sleep(0.2)  # stay well under SEC's 10 requests/second limit
    return r


def latest_10k(company: Company) -> dict:
    sub = _get(f"https://data.sec.gov/submissions/CIK{company.cik:010d}.json").json()
    r = sub["filings"]["recent"]
    for i, form in enumerate(r["form"]):
        if form == "10-K":
            return {"accession": r["accessionNumber"][i], "filed": r["filingDate"][i],
                    "period_end": r["reportDate"][i], "primary_doc": r["primaryDocument"][i]}
    raise LookupError(f"No 10-K found for {company.ticker}")


def ground_truth_from_facts(facts: dict, accession: str, period_end: str) -> dict:
    """Pick, for each metric, the full-fiscal-year value reported in this exact filing."""
    out = {}
    gaap = facts["facts"]["us-gaap"]
    for concept, metric in METRICS.items():
        if concept not in gaap:
            continue
        unit, rows = next(iter(gaap[concept]["units"].items()))
        rows = [x for x in rows if x["accn"] == accession and x["end"] == period_end]
        # duration facts: keep the ~1-year period; instant facts have no start
        annual = [x for x in rows if "start" not in x or _days(x["start"], x["end"]) > 300]
        if annual:
            out[metric] = {"value": annual[-1]["val"], "unit": unit, "concept": concept}
    return out


def _days(start: str, end: str) -> int:
    from datetime import date
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def fetch(company: Company) -> None:
    meta = latest_10k(company)
    folder = DATA_DIR / company.ticker
    folder.mkdir(parents=True, exist_ok=True)
    acc = meta["accession"].replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{company.cik}/{acc}/{meta['primary_doc']}"
    (folder / "10k.htm").write_bytes(_get(url).content)
    facts = _get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{company.cik:010d}.json").json()
    truth = ground_truth_from_facts(facts, meta["accession"], meta["period_end"])
    (folder / "filing.json").write_text(json.dumps({**meta, "url": url, "company": company.name,
                                                    "ticker": company.ticker}, indent=2))
    (folder / "ground_truth.json").write_text(json.dumps(truth, indent=2))
    print(f"{company.ticker}: 10-K for period ending {meta['period_end']} "
          f"({len(truth)} ground-truth metrics) -> {folder}")


if __name__ == "__main__":
    for t in sys.argv[1:] or list(COMPANIES):
        fetch(COMPANIES[t.upper()])
