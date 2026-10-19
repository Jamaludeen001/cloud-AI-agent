# app/api/routes_health.py
from fastapi import APIRouter

from app.services.sessions import health as sessions_health

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz():
    return {"status": "ok"}


@router.get("/readyz")
async def readyz():
    checks = sessions_health()
    return {"ready": all(checks.values()), "checks": checks}