# app/services/llm.py
from __future__ import annotations

import logging
import time
from typing import Any, List, Optional

from app.config import config

logger = logging.getLogger(__name__)


class LLMResult:
    def __init__(self, text: str, tool_calls: list, tokens: int, raw: Any):
        self.text = text
        self.tool_calls = tool_calls or []
        self.tokens = tokens
        self.raw = raw


class BudgetGuard:
    def __init__(self, max_calls: int, max_tokens: int, max_seconds: float):
        self.max_calls = max_calls
        self.max_tokens = max_tokens
        self.max_seconds = max_seconds
        self.calls = 0
        self.tokens = 0
        self.started = time.time()

    def check(self) -> None:
        if self.calls >= self.max_calls:
            raise RuntimeError(f"Budget: llm_calls={self.calls}")
        if self.tokens >= self.max_tokens:
            raise RuntimeError(f"Budget: tokens={self.tokens}")
        if time.time() - self.started >= self.max_seconds:
            raise RuntimeError("Budget: time")

    def record(self, tokens: int) -> None:
        self.calls += 1
        self.tokens += tokens


class LLMClient:
    def __init__(self, llm, guard: BudgetGuard):
        self.llm = llm
        self.guard = guard

    def invoke(self, messages: List[Any], tools: Optional[list] = None) -> LLMResult:
        self.guard.check()

        bound = self.llm
        if tools:
            try:
                bound = self.llm.bind_tools(tools)
            except Exception as e:
                logger.warning("[llm] bind_tools failed: %s", e)

        last_err = None
        for attempt in range(config.llm_max_retries):
            try:
                out = bound.invoke(messages)
                result = self._wrap(out)
                self.guard.record(result.tokens)
                return result
            except Exception as e:
                err = str(e)
                if "429" in err or "rate_limit" in err.lower():
                    raise RuntimeError(f"Rate limit: {err[:200]}")
                last_err = e
                if attempt < config.llm_max_retries - 1:
                    time.sleep(0.3 * (2 ** attempt))

        raise RuntimeError(f"LLM failed after retries: {last_err}")

    @staticmethod
    def _wrap(out) -> LLMResult:
        text = getattr(out, "content", "") or ""
        if isinstance(text, list):
            text = " ".join(
                c.get("text", "") if isinstance(c, dict) else str(c) for c in text
            )
        tool_calls = getattr(out, "tool_calls", None) or []
        usage = getattr(out, "usage_metadata", None) or {}
        tokens = usage.get("total_tokens", 0) if isinstance(usage, dict) else 0
        return LLMResult(text=str(text), tool_calls=tool_calls, tokens=tokens, raw=out)