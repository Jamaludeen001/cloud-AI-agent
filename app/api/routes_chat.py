# app/api/routes_chat.py
import logging

from fastapi import APIRouter, HTTPException

from app.api.schemas import ChatRequest, ChatResponse, CreateSessionResponse
from app.graph.runner import get_runner
from app.services.sessions import get_session, save_session, create_session, append_turn

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_new_session():
    """Generates a new session ID for an external application."""
    session = create_session()
    return CreateSessionResponse(session_id=session["session_id"])


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not req.session_id:
        raise HTTPException(status_code=400, detail="session_id is required. Call /api/sessions first.")

    session = get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired.")

    runner = get_runner()
    try:
        result = runner.invoke(session["session_id"], req.question)
    except Exception as e:
        logger.exception("chat failed")
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)[:200]}")

    answer = result.get("final_answer") or ""
    append_turn(session["session_id"], req.question, answer)

    return ChatResponse(
        session_id=session["session_id"],
        run_id=result.get("run_id", ""),
        status=result.get("status", "unknown"),
        route=result.get("route"),
        answer=answer,
        sources=result.get("chunks", []),
        steps=result.get("steps", []),
        meta={
            "llm_calls": result.get("llm_calls", 0),
            "llm_tokens": result.get("llm_tokens", 0),
        },
    )