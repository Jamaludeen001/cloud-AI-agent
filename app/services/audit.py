# app/services/audit.py
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def record_run(state: Dict[str, Any]) -> None:
    logger.info(
        "[audit] run=%s session=%s route=%s status=%s steps=%d tokens=%d calls=%d",
        state.get("run_id"),
        state.get("session_id"),
        state.get("route"),
        state.get("status"),
        len(state.get("steps", [])),
        state.get("llm_tokens", 0),
        state.get("llm_calls", 0),
    )