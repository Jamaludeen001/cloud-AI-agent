# app/api/schemas.py
from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    session_id: str = Field(description="The active session ID")
    question: str = Field(min_length=1, max_length=4000)

class ChatResponse(BaseModel):
    session_id: str
    run_id: str
    status: str
    route: Optional[str] = None
    answer: str
    sources: List[Dict[str, Any]] = []
    steps: List[Dict[str, Any]] = []
    meta: Dict[str, Any] = {}

class CreateSessionResponse(BaseModel):
    session_id: str

class URLRequest(BaseModel):
    session_id: str
    url: str = ""
    text_limit: int = 20000

class PasteRequest(BaseModel):
    session_id: str
    text: str
    text_limit: int = 20000

class RemoveRequest(BaseModel):
    session_id: str

class AttachResponse(BaseModel):
    session_id: str
    chunk_count: int
    source_label: str
    index_type: str = "unknown"