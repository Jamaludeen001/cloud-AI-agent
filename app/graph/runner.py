# app/graph/runner.py
import logging
import time
import uuid
from typing import Any, AsyncIterator, Dict, Optional

from app.config import config
from app.graph.builder import build_graph

logger = logging.getLogger(__name__)


class GraphRunner:
    def __init__(self):
        self.graph = build_graph()

    def _config(self, session_id: str, run_id: str) -> dict:
        return {
            "configurable": {"thread_id": session_id},
            "run_id": run_id,
            "recursion_limit": 15,  # Allow multi-step tool calls
        }

    def _initial_state(self, session_id: str, question: str) -> Dict[str, Any]:
        from app.services.sessions import get_session
        session = get_session(session_id)
        history = session.get("history", [])[-10:]

        return {
            "session_id": session_id,
            "run_id": str(uuid.uuid4()),
            "user_query": question,
            "history": history,
            "messages": [],     # Start empty; tools will append here
            "route": None,
            "draft_answer": None,
            "final_answer": None,
            "steps": [],
            "llm_calls": 0,
            "llm_tokens": 0,
            "started_at": time.time(),
            "ended_at": None,
            "status": "in_progress",
            "error": None,
            "max_llm_calls": 4,
            "max_tokens": 8000,
            "max_seconds": 30.0,
        }

    def invoke(self, session_id: str, question: str) -> Dict[str, Any]:
        state = self._initial_state(session_id, question)
        cfg = self._config(session_id, state["run_id"])
        
        return self.graph.invoke(state, config=cfg)

    async def astream(self, session_id: str, question: str) -> AsyncIterator[Dict[str, Any]]:
        state = self._initial_state(session_id, question)
        cfg = self._config(session_id, state["run_id"])
        
        async for event in self.graph.astream_events(state, config=cfg, version="v2"):
            kind = event.get("event")
            if kind in ("on_chain_start", "on_chain_end"):
                yield {
                    "event": kind,
                    "name": event.get("name"),
                    "data": event.get("data", {}),
                }

    def get_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        cfg = {"configurable": {"thread_id": session_id}}
        snap = self.graph.get_state(cfg)
        return snap.values if snap else None

    def resume(self, session_id: str, update: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        cfg = {"configurable": {"thread_id": session_id}}
        if update:
            self.graph.update_state(cfg, update)
        return self.graph.invoke(None, config=cfg)


_runner: Optional[GraphRunner] = None


def get_runner() -> GraphRunner:
    global _runner
    if _runner is None:
        _runner = GraphRunner()
    return _runner