"""Tests run without an API key: a scripted fake model stands in for the real one."""

import json
from pathlib import Path

import pytest

from finaudit import bias
from finaudit.document import load_pages
from finaudit.llm import FakeClient
from finaudit.pipeline import FinAudit
from finaudit.retrieval import BM25Retriever
from finaudit.sec import ground_truth_from_facts
from finaudit.verify import extract_numbers, is_refusal, numeric_verdict, parse_judgement

FIX = Path(__file__).parent / "fixtures"
FILING = json.loads((FIX / "filing.json").read_text())


@pytest.fixture
def pages():
    return load_pages(FIX / "mini_10k.htm")


# ---- Document parsing ------------------------------------------------------ #
def test_splits_on_page_breaks_and_drops_tiny_pages(pages):
    assert [p.number for p in pages] == [1, 2, 3, 4]       # page 5 ("short") dropped
    assert "167,000 full-time equivalent employees" in pages[1].text


def test_hidden_xbrl_header_removed(pages):
    assert "hidden machine-readable header" not in pages[0].text


# ---- Retrieval --------------------------------------------------------------- #
def test_bm25_finds_the_right_page(pages):
    r = BM25Retriever(pages)
    assert r.top_k("How much did Apple spend on research and development?", 1)[0].number == 4
    assert r.top_k("How many full-time equivalent employees?", 1)[0].number == 2


# ---- Ground truth from XBRL ----------------------------------------------- #
def test_ground_truth_picks_annual_value_from_this_filing():
    facts = json.loads((FIX / "companyfacts_subset.json").read_text())
    gt = ground_truth_from_facts(facts, "0000320193-26-000026", "2026-09-26")
    # the annual figure, not the quarter or the prior year
    assert gt["research_and_development"]["value"] == 45_765_000_000
    assert gt["cash_and_equivalents"]["value"] == 36_305_000_000       # instant fact
    assert gt["diluted_eps"]["value"] == 8.98


# ---- Numeric verification ------------------------------------------------- #
@pytest.mark.parametrize("answer,expected", [
    ("Apple spent $45,765 million on R&D [p. 34].", "CORRECT"),
    ("R&D expense was $45.8 billion.", "CORRECT"),
    ("Research and development was 45,765 [p. 34]", "CORRECT"),        # table units: millions
    ("R&D expense was $34,550 million.", "WRONG_NUMBER"),              # the prior-year figure
    ("R&D was significant in fiscal 2026 [p. 34].", "NO_NUMBER"),     # year and page ignored
    ("Not found in document", "REFUSED"),
])
def test_numeric_verdict(answer, expected):
    assert numeric_verdict(answer, 45_765_000_000) == expected


def test_extract_numbers_scales_units():
    assert extract_numbers("$1.5 billion and 300 million") == [1.5e9, 300e6]


def test_eps_matches():
    assert numeric_verdict("Diluted EPS was $8.98 [p. 34].", 8.98) == "CORRECT"


def test_refusal_detection():
    assert is_refusal("I don't know")
    assert is_refusal("Not found in document.")
    assert not is_refusal("Net income was $132,175 million.")


# ---- Judge parsing ------------------------------------------------------- #
def test_parse_judgement():
    j = parse_judgement("VERDICT: HALLUCINATED\nREASON: The figure is from the prior year.")
    assert j.verdict == "HALLUCINATED" and "prior year" in j.reason
    assert parse_judgement("I think it's fine").verdict == "UNPARSEABLE"


@pytest.mark.parametrize("raw", [
    "**VERDICT:** GROUNDED\n**REASON:** Matches p. 29.",
    "Verdict: Grounded\nReason: Matches p. 29.",
    "## Verdict\nGROUNDED\n\n## Reason\nMatches p. 29.",
    "VERDICT - GROUNDED. REASON: Matches p. 29.",
])
def test_parse_judgement_tolerates_formatting(raw):
    """Formats seen from real judge replies, or plausible variants of them."""
    j = parse_judgement(raw)
    assert j.verdict == "GROUNDED" and "p. 29" in j.reason


# ---- Pipeline: retry and audit log ---------------------------------------- #
def test_grounded_answer_is_not_retried(pages, tmp_path):
    fake = FakeClient(["Net income was $132,175 million [p. 4].",
                       "VERDICT: GROUNDED\nREASON: Matches the income statement."])
    fa = FinAudit("AAPL", fake, pages=pages, filing=FILING, log_path=tmp_path / "log.jsonl")
    res = fa.ask("What was Apple's net income?")
    assert len(res.attempts) == 1 and res.final.verdict == "GROUNDED"
    assert len(fake.calls) == 2


def test_hallucination_triggers_one_reflection_retry(pages, tmp_path):
    fake = FakeClient([
        "Net income was $112,010 million.",                              # prior-year figure
        "VERDICT: HALLUCINATED\nREASON: 112,010 is the fiscal 2025 figure.",
        "Net income was $132,175 million [p. 4].",
        "VERDICT: GROUNDED\nREASON: Matches the fiscal 2026 column.",
    ])
    log = tmp_path / "log.jsonl"
    fa = FinAudit("AAPL", fake, pages=pages, filing=FILING, log_path=log)
    res = fa.ask("What was Apple's net income?")
    assert [a.verdict for a in res.attempts] == ["HALLUCINATED", "GROUNDED"]
    assert "fiscal 2025 figure" in fake.calls[2]["user"]         # the retry sees the judge's reason

    entry = json.loads(log.read_text().splitlines()[0])
    for key in ["timestamp", "prompt_version", "accession", "question", "pages_used",
                "answer_model", "judge_model", "final_verdict", "retried", "attempts"]:
        assert key in entry
    assert entry["retried"] is True and len(entry["attempts"]) == 2


def test_judge_is_a_different_model(pages, tmp_path):
    fake = FakeClient(["Not found in document", "VERDICT: REFUSED\nREASON: none"])
    FinAudit("AAPL", fake, pages=pages, filing=FILING,
             log_path=tmp_path / "l.jsonl").ask("stock price today")
    assert fake.calls[0]["model"] != fake.calls[1]["model"]   # judge is a different model


# ---- Bias summary ------------------------------------------------------- #
def test_bias_summary_counts_confidently_wrong():
    rows = [{"answered": True, "numeric": "CORRECT"},
            {"answered": True, "numeric": "WRONG_NUMBER"},
            {"answered": False, "numeric": "REFUSED"}]
    s = bias.summarize(rows)
    assert s["answered"] == 2 and s["confidently_wrong"] == 1 and s["accuracy_when_answered"] == 0.5


def test_reason_spanning_lines_is_kept_whole():
    j = parse_judgement("VERDICT: GROUNDED\n"
                        "REASON: The $45,765 million R&D figure,\nmatches page 29.")
    assert j.reason == "The $45,765 million R&D figure, matches page 29."
