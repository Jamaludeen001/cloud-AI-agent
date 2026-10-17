# app/api/routes_chat.py
import logging

from fastapi import APIRouter, HTTPException

from app.api.schemas import ChatRequest, ChatResponse
from app.graph.runner import get_runner
from app.services.sessions import get_session, save_session, create_session, append_turn

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if req.session_id:
        session = get_session(req.session_id)
    else:
        session = create_session()
    save_session(session["session_id"], session)

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