# app/main.py
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import config
from app.logging_config import setup_logging
from app.api.routes_health import router as health_router
from app.api.routes_chat import router as chat_router
from app.api.routes_session import router as session_router

setup_logging(config.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[startup] env=%s model=%s", config.env, config.llm_model)
    from app.graph.runner import get_runner
    get_runner()
    logger.info("[startup] graph ready")
    yield
    logger.info("[shutdown]")


app = FastAPI(title="Agent App", lifespan=lifespan)

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(session_router)

try:
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
except Exception as e:
    logger.warning("Static mount failed: %s", e)