# app/services/retrieval.py
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.config import config
from app.knowledge.embedder import Embedder, Reranker

logger = logging.getLogger(__name__)

_embedder = None
_reranker = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder


def _get_reranker():
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker


def retrieve_chunks(session: Dict[str, Any], query: str) -> List[Dict[str, Any]]:
    index = session.get("index")
    chunks = session.get("chunks", [])
    if index is None or not chunks:
        return []

    embedder = _get_embedder()
    q_vec = embedder.embed_query(query).reshape(1, -1).astype("float32")

    top_k = min(config.top_k_retrieve, len(chunks))
    scores, indices = index.search(q_vec, top_k)

    candidates = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(chunks):
            continue
        c = dict(chunks[idx])
        c["score"] = float(score)
        candidates.append(c)

    # Skip rerank for small corpora (latency tradeoff)
    if len(chunks) < config.rerank_threshold:
        return candidates[: config.top_k_rerank]

    try:
        reranker = _get_reranker()
        pairs = [(query, c["chunk"]) for c in candidates]
        rerank_scores = reranker.predict(pairs)
        ranked = sorted(
            ({"score": float(s), **c} for s, c in zip(rerank_scores, candidates)),
            key=lambda x: x["score"],
            reverse=True,
        )
        return ranked[: config.top_k_rerank]
    except Exception as e:
        logger.warning("[retrieval] rerank failed, using FAISS order: %s", e)
        return candidates[: config.top_k_rerank]


def recall_memory(session: Dict[str, Any], query: str) -> List[Dict[str, Any]]:
    history = session.get("history", [])
    if not history:
        return []
    recent = history[-5:]
    return [{"text": f"Q: {t['q']}\nA: {t['a']}"} for t in recent]