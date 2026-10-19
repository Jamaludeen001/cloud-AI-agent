# app/api/routes_session.py
import logging
import os
import tempfile
from pathlib import Path
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.api.schemas import AttachResponse, PasteRequest, URLRequest, RemoveRequest
from app.knowledge.fetcher import fetch_from_file
from app.services.ingest import ingest_url, ingest_text
from app.services.sessions import get_session, save_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/session", tags=["session"])

def _store_result(session_id: str, result: dict) -> dict:
    session = get_session(session_id)
    # Save LlamaIndex instead of FAISS
    session["llama_index"] = result["llama_index"]
    session["source_label"] = result["source_label"]
    save_session(session["session_id"], session)
    return session

@router.post("/url", response_model=AttachResponse)
async def attach_url(req: URLRequest):
    if not req.url:
        raise HTTPException(status_code=400, detail="URL is required.")
    try:
        result = ingest_url(req.url, req.text_limit)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    session = _store_result(req.session_id, result)
    return AttachResponse(
        session_id=session["session_id"],
        chunk_count=1, 
        source_label=result["source_label"],
        index_type="LlamaIndex"
    )

@router.post("/paste", response_model=AttachResponse)
async def attach_paste(req: PasteRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text is required.")
    try:
        result = ingest_text(req.text, req.text_limit, label="pasted text")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    session = _store_result(req.session_id, result)
    return AttachResponse(
        session_id=session["session_id"],
        chunk_count=1,
        source_label=result["source_label"],
        index_type="LlamaIndex"
    )

@router.post("/file", response_model=AttachResponse)
async def attach_file(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    text_limit: int = Form(20000),
):
    suffix = Path(file.filename or "").suffix.lower()
    if not suffix:
        ct = (file.content_type or "").lower()
        suffix = ".pdf" if "pdf" in ct else ".txt"

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = tmp.name
            content = await file.read()
            tmp.write(content)

        raw_text = fetch_from_file(tmp_path, text_limit)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    try:
        result = ingest_text(raw_text, text_limit, label=file.filename or "file")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    session = _store_result(session_id, result)
    return AttachResponse(
        session_id=session["session_id"],
        chunk_count=1, 
        source_label=result["source_label"],
        index_type="LlamaIndex"
    )

@router.post("/remove")
async def remove_data(req: RemoveRequest):
    session = get_session(req.session_id)
    session["llama_index"] = None
    session["source_label"] = None
    save_session(session["session_id"], session)
    return {"ok": True}