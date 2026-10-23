# app/api/routes_chat.py
import logging
import time

from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.api.schemas import ChatRequest, ChatResponse, CreateSessionResponse
from app.graph.runner import get_runner
from app.services.sessions import get_session, save_session, create_session, append_turn
from app.services.dynamo_logger import log_chat_to_dynamo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_new_session():
    """Generates a new session ID for an external application."""
    session = create_session()
    return CreateSessionResponse(session_id=session["session_id"])


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, background_tasks: BackgroundTasks):
    if not req.session_id:
        raise HTTPException(status_code=400, detail="session_id is required. Call /api/sessions first.")

    session = get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired.")

    runner = get_runner()
    
    # 1. Start the timer
    start_time = time.perf_counter() 
    
    try:
        result = runner.invoke(session["session_id"], req.question)
    except Exception as e:
        logger.exception("chat failed")
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)[:200]}")

    # 2. Stop the timer and calculate duration
    end_time = time.perf_counter()
    duration_ms = (end_time - start_time) * 1000

    answer = result.get("final_answer") or ""
    route = result.get("route", "unknown")
    status = result.get("status", "unknown")
    run_id = result.get("run_id", "unknown")

    append_turn(session["session_id"], req.question, answer)

    # 3. Hand off the DynamoDB write to the background
    background_tasks.add_task(
        log_chat_to_dynamo,
        session_id=session["session_id"],
        run_id=run_id,
        question=req.question,
        answer=answer,
        duration_ms=duration_ms,
        route=route,
        status=status
    )

    # 4. Return response immediately (User doesn't wait for DB write)
    return ChatResponse(
        session_id=session["session_id"],
        run_id=run_id,
        status=status,
        route=route,
        answer=answer,
        sources=result.get("chunks", []),
        steps=result.get("steps", []),
        meta={
            "llm_calls": result.get("llm_calls", 0),
            "llm_tokens": result.get("llm_tokens", 0),
        },
    )
