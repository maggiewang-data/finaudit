"""Append-only audit log: one JSON line per question, written before anything is shown.

Each entry records enough to reconstruct the decision later: which filing,
which pages the model saw, which model versions answered and judged, both
attempts if a retry happened, and the cost. A hash of the prompt shows
whether two runs used the same instructions.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from . import prompts


def prompt_version() -> str:
    blob = (prompts.ANSWER_SYSTEM + prompts.JUDGE_SYSTEM + prompts.JUDGE_USER).encode()
    return hashlib.sha256(blob).hexdigest()[:10]


def write(entry: dict, path: Path) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "prompt_version": prompt_version(), **entry}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record
