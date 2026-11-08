"""Settings. Secrets come from the environment (or a local .env file), never from code."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
AUDIT_LOG = RESULTS_DIR / "audit_log.jsonl"

load_dotenv(ROOT / ".env")

# Model used to answer questions, and (separately) the model used as the judge.
# Using a different judge model reduces the chance the judge simply agrees with
# its own family's mistakes.
ANSWER_MODEL = os.getenv("FINAUDIT_ANSWER_MODEL", "claude-sonnet-5-5")
JUDGE_MODEL = os.getenv("FINAUDIT_JUDGE_MODEL", "claude-haiku-5-5")

# SEC asks automated clients to identify themselves: "Name email@example.com"
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "")

TOP_K = 3                 # pages retrieved per question
MAX_CONTEXT_CHARS = 2500  # per retrieved page, keeps prompts comparable and cheap
MAX_RETRIES = 1           # reflection retries after a failed groundedness check
NOT_FOUND = "Not found in document"


@dataclass(frozen=True)
class Company:
    ticker: str
    name: str
    cik: int


# A large, highly visible company and a small, rarely discussed one in a related
# industry (consumer electronics), used for the representation-bias probe.
LARGE_CAP = Company("AAPL", "Apple Inc.", 320193)
SMALL_CAP = Company("UEIC", "Universal Electronics Inc.", 101984)
COMPANIES = {c.ticker: c for c in (LARGE_CAP, SMALL_CAP)}
