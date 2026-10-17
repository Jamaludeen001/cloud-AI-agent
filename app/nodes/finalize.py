# app/nodes/finalize.py
from __future__ import annotations

import logging
import time
from typing import Any, Dict

from app.graph.state import AgentState
from app.services.audit import record_run

logger = logging.getLogger(__name__)


def finalize_node(state: AgentState, config: dict = None) -> Dict[str, Any]:
    started = time.time()

    fallback = state.get("final_answer")
    if not fallback:
        status = state.get("status", "failed")
        if status != "completed":
            fallback = ("I couldn't produce a reliable answer. "
                        "Please rephrase or narrow the question.")
        else:
            fallback = ""

    ended = time.time()
    step = {
        "name": "finalize",
        "started_at": started,
        "ended_at": ended,
        "input": {},
        "output": {"status": state.get("status")},
        "error": None,
        "duration_ms": int((ended - started) * 1000),
    }

    try:
        record_run(state)
    except Exception as e:
        logger.warning("[finalize] audit failed (non-fatal): %s", e)

    return {
        "final_answer": fallback,
        "ended_at": ended,
        "steps": [step],
    }