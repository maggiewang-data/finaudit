"""Two independent ways to check an answer.

1. LLM-as-judge: reads the answer next to the retrieved excerpts and says
   whether it's supported. Flexible, but it is itself a model and can be wrong.
2. Numeric ground truth: compares the numbers in the answer with the company's
   own XBRL figures from the same filing. Narrow, but it can't be talked into
   agreeing.

Running both lets the project measure how often the judge is right, rather
than assuming it is.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .config import NOT_FOUND

SCALE = {"thousand": 1e3, "k": 1e3, "million": 1e6, "mn": 1e6, "m": 1e6,
         "billion": 1e9, "bn": 1e9, "b": 1e9, "trillion": 1e12}
NUMBER = re.compile(
    r"(?P<neg>\(|-)?\$?\s?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s?"
    r"(?P<unit>thousand|million|billion|trillion|mn|bn|[kmb])?\b(?!\s?%)", re.I)
REFUSAL = re.compile(r"not found in (the )?document|i don.?t know|not (provided|available|"
                     r"included|mentioned) in the (excerpts|document)", re.I)
YEAR_LIKE = re.compile(r"^(19|20)\d{2}$")


@dataclass
class Judgement:
    verdict: str   # GROUNDED | PARTIAL | HALLUCINATED | REFUSED | UNPARSEABLE
    reason: str


VERDICT_RE = re.compile(r"verdict\W*(GROUNDED|PARTIAL|HALLUCINATED|REFUSED)", re.I)
REASON_RE = re.compile(r"reason\W*:?\W*(.+)", re.I | re.S)


def parse_judgement(text: str) -> Judgement:
    """Read the judge's verdict even when it adds formatting like **VERDICT:** or
    'Verdict - Grounded'. Models don't always follow an output format exactly, so
    the parser looks for the pattern instead of an exact line prefix."""
    clean = text.replace("*", "").replace("#", "").replace("`", "")
    v = VERDICT_RE.search(clean)
    r = REASON_RE.search(clean)
    reason = " ".join(r.group(1).split())[:400] if r else ""
    return Judgement(v.group(1).upper() if v else "UNPARSEABLE", reason)


def is_refusal(answer: str) -> bool:
    return bool(REFUSAL.search(answer)) or answer.strip().rstrip(".") == NOT_FOUND


def extract_numbers(text: str) -> list[float]:
    """All numbers in the text, scaled by any unit word that follows them.
    Page citations like [p. 34] and bare years like 2026 are ignored."""
    text = re.sub(r"\[p+\.?\s*\d+(?:[-,]\s*\d+)*\]", " ", text, flags=re.I)
    out = []
    for m in NUMBER.finditer(text):
        raw = m.group("num")
        if YEAR_LIKE.match(raw):
            continue
        val = float(raw.replace(",", ""))
        unit = (m.group("unit") or "").lower()
        val *= SCALE.get(unit, 1.0)
        out.append(-val if m.group("neg") else val)
    return out


def numeric_verdict(answer: str, truth_value: float | None, rel_tol: float = 0.005) -> str:
    """CORRECT | WRONG_NUMBER | NO_NUMBER | REFUSED | NO_TRUTH.

    Filings state tables "in millions", so an answer of "$45,765" for a
    $45.8 billion figure is also accepted when no unit word was given: the
    candidate is tried at face value, x1,000 and x1,000,000.
    """
    if is_refusal(answer):
        return "REFUSED"
    if truth_value is None:
        return "NO_TRUTH"
    nums = extract_numbers(answer)
    if not nums:
        return "NO_NUMBER"
    target = abs(truth_value)
    for n in nums:
        for scale in (1, 1e3, 1e6):
            if target and abs(abs(n) * scale - target) / target <= rel_tol:
                return "CORRECT"
    return "WRONG_NUMBER"
