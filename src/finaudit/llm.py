"""Thin wrapper around the model API, plus a scripted fake for tests.

Raw API calls, no framework: every prompt and response is visible and logged.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Protocol


@dataclass
class LLMResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_s: float


class LLMClient(Protocol):
    def complete(self, system: str, user: str, model: str,
                 max_tokens: int = 600) -> LLMResponse: ...


class AnthropicClient:
    def __init__(self):
        import anthropic
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError("Set ANTHROPIC_API_KEY in .env")
        self.client = anthropic.Anthropic()

    def complete(self, system: str, user: str, model: str, max_tokens: int = 600) -> LLMResponse:
        t0 = time.perf_counter()
        msg = self.client.messages.create(
            model=model, max_tokens=max_tokens, temperature=0,
            system=system, messages=[{"role": "user", "content": user}])
        text = "".join(b.text for b in msg.content if b.type == "text")
        return LLMResponse(text, model, msg.usage.input_tokens, msg.usage.output_tokens,
                           time.perf_counter() - t0)


class FakeClient:
    """Returns scripted responses in order; records every call. Used in tests."""

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def complete(self, system: str, user: str, model: str, max_tokens: int = 600) -> LLMResponse:
        self.calls.append({"system": system, "user": user, "model": model})
        return LLMResponse(self.responses.pop(0), model, len(user) // 4, 50, 0.0)
