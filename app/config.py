# app/config.py
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Load .env BEFORE reading any env vars
load_dotenv()


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


@dataclass(frozen=True)
class Config:
    # Runtime
    env: str = _env("APP_ENV", "dev")
    log_level: str = _env("LOG_LEVEL", "INFO")

    # LLM
    llm_provider: str = _env("LLM_PROVIDER", "google")
    llm_model: str = _env("LLM_MODEL", "gemini-1.5-flash")
    llm_api_key: str = _env("GOOGLE_API_KEY", "")
    llm_max_retries: int = int(_env("LLM_MAX_RETRIES", "2"))
    llm_timeout_s: float = float(_env("LLM_TIMEOUT_S", "60"))

    # Budgets
    max_llm_calls: int = int(_env("MAX_LLM_CALLS", "4"))
    max_tokens: int = int(_env("MAX_TOKENS", "8000"))
    max_seconds: float = float(_env("MAX_SECONDS", "30"))

    # State
    redis_url: str = _env("REDIS_URL", "")
    checkpoint_ttl: int = int(_env("CHECKPOINT_TTL", "86400"))
    session_ttl: int = int(_env("SESSION_TTL", "604800"))

    # Retrieval
    top_k_retrieve: int = int(_env("TOP_K_RETRIEVE", "10"))
    top_k_rerank: int = int(_env("TOP_K_RERANK", "5"))
    rerank_threshold: int = int(_env("RERANK_THRESHOLD", "200"))

    # Fetching
    default_timeout: float = float(_env("DEFAULT_TIMEOUT", "30"))
    max_bytes: int = int(_env("MAX_BYTES", "5000000"))

    # Observability
    langsmith_api_key: str = _env("LANGSMITH_API_KEY", "")
    langsmith_project: str = _env("LANGSMITH_PROJECT", "agent-app")


config = Config()