# app/graph/state.py
from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langgraph.graph.message import add_messages


def merge_list(left: list, right: list) -> list:
    return (left or []) + (right or [])


def keep_last(left: Any, right: Any) -> Any:
    return right if right is not None else left


class AgentState(TypedDict, total=False):
    # Identity
    session_id: str
    run_id: str
    user_query: str

    # Conversation
    messages: Annotated[list, add_messages]
    history: Annotated[List[Dict[str, Any]], keep_last]

    # Routing
    route: Optional[str]

    # Retrieved
    chunks: Annotated[List[Dict[str, Any]], merge_list]
    memory_hits: Annotated[List[Dict[str, Any]], merge_list]

    # Outputs
    draft_answer: Annotated[Optional[str], keep_last]
    final_answer: Annotated[Optional[str], keep_last]

    # Observability
    steps: Annotated[List[Dict[str, Any]], merge_list]
    llm_calls: Annotated[int, keep_last]
    llm_tokens: Annotated[int, keep_last]
    started_at: Annotated[float, keep_last]
    ended_at: Annotated[Optional[float], keep_last]

    # Status
    status: Annotated[str, keep_last]
    error: Annotated[Optional[str], keep_last]

    # Budgets
    max_llm_calls: Annotated[int, keep_last]
    max_tokens: Annotated[int, keep_last]
    max_seconds: Annotated[float, keep_last]