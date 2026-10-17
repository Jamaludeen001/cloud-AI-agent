# app/nodes/route.py
import logging
import time
from typing import Any, Dict
from app.graph.state import AgentState
from app.routing.classifier import classify
from app.routing.handlers import reply_for
from app.services.sessions import get_session

logger = logging.getLogger(__name__)

DETERMINISTIC = {"greeting", "gratitude", "acknowledgment", "farewell", "identity", "meta"}

def route_node(state: AgentState, config: dict = None) -> Dict[str, Any]:
    started = time.time()
    question = state.get("user_query", "")
    session_id = state.get("session_id", "")
    session = get_session(session_id)
    
    has_data = bool(session.get("chunks"))
    has_history = len(session.get("history", [])) > 0

    intent, source = classify(question)

    step = {
        "name": "route",
        "started_at": started,
        "ended_at": time.time(),
        "input": {"q": question[:80]},
        "output": {"intent": intent, "source": source},
        "duration_ms": int((time.time() - started) * 1000),
    }

    logger.info(f"[route] intent={intent} source={source}")

    # Deterministic intents (instant reply)
    if intent in DETERMINISTIC:
        return {
            "route": intent,
            "final_answer": reply_for(intent, has_history, has_data),
            "status": "completed",
            "steps": [step],
        }

    # Everything else goes to the ReAct loop
    return {"route": "react_loop", "steps": [step]}