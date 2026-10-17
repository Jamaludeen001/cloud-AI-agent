# app/services/sessions.py
from __future__ import annotations

import json
import logging
import pickle
import threading
import uuid
from typing import Any, Dict, Optional

import numpy as np
import faiss

from app.config import config

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_mem: Dict[str, Dict[str, Any]] = {}

_redis = None
if config.redis_url:
    try:
        import redis
        _redis = redis.from_url(config.redis_url, decode_responses=False)
        _redis.ping()
        logger.info("[sessions] Redis connected")
    except Exception as e:
        logger.warning("[sessions] Redis unavailable: %s", e)
        _redis = None


def _new_session(session_id: Optional[str] = None) -> Dict[str, Any]:
    return {
        "session_id": session_id or str(uuid.uuid4()),
        "chunks": [],
        "index": None,
        "embeddings": None,
        "history": [],
        "source_label": None,
    }


def get_session(session_id: Optional[str]) -> Dict[str, Any]:
    if not session_id:
        return _new_session()

    if _redis is not None:
        raw = _redis.get(f"session:{session_id}")
        if not raw:
            return _new_session(session_id)
        session = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)

        idx_bytes = _redis.get(f"index:{session_id}")
        if idx_bytes:
            arr = np.frombuffer(idx_bytes, dtype="uint8")
            session["index"] = faiss.deserialize_index(arr)

        emb_bytes = _redis.get(f"emb:{session_id}")
        if emb_bytes:
            session["embeddings"] = pickle.loads(emb_bytes)

        return session

    with _lock:
        return _mem.get(session_id) or _new_session(session_id)


def save_session(session_id: str, session: Dict[str, Any]) -> None:
    if _redis is not None:
        index = session.get("index")
        embeddings = session.get("embeddings")

        if index is not None:
            serialized = faiss.serialize_index(index).tobytes()
            _redis.setex(f"index:{session_id}", config.session_ttl, serialized)
        if embeddings is not None:
            _redis.setex(f"emb:{session_id}", config.session_ttl,
                         pickle.dumps(embeddings))

        json_safe = {k: v for k, v in session.items()
                     if k not in ("index", "embeddings")}
        _redis.setex(f"session:{session_id}", config.session_ttl,
                     json.dumps(json_safe, default=str))
        return

    with _lock:
        _mem[session_id] = session


def create_session() -> Dict[str, Any]:
    s = _new_session()
    save_session(s["session_id"], s)
    return s


def append_turn(session_id: str, question: str, answer: str) -> None:
    s = get_session(session_id)
    s.setdefault("history", []).append({"q": question, "a": answer})
    save_session(session_id, s)


def health() -> Dict[str, bool]:
    return {
        "session_store": _redis is not None or True,
        "redis": _redis is not None or config.redis_url == "",
    }