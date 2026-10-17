# app/graph/checkpointer.py
from __future__ import annotations

import logging

from app.config import config

logger = logging.getLogger(__name__)


def build_checkpointer():
    if not config.redis_url:
        from langgraph.checkpoint.memory import MemorySaver
        logger.warning("[checkpointer] Using in-memory (dev only)")
        return MemorySaver()

    try:
        from langgraph.checkpoint.redis import RedisSaver
        saver = RedisSaver.from_conn_string(config.redis_url)
        saver.setup()
        logger.info("[checkpointer] Redis checkpointer ready")
        return saver
    except Exception as e:
        logger.error("[checkpointer] Redis failed, falling back: %s", e)
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()