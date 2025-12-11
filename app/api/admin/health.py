# app/api/admin/health.py
"""
Health endpoints for shallow and deep readiness checks.
"""
from fastapi import APIRouter, HTTPException
from starlette.status import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE

from app.db.session import check_db_ready

router = APIRouter(prefix="/admin", tags=["health"])


@router.get("/health", status_code=HTTP_200_OK)
async def health() -> dict:
    """Shallow health endpoint."""
    return {"status": "ok", "version": "1.0.0"}


@router.get("/health/deep", status_code=HTTP_200_OK)
async def health_deep() -> dict:
    """Deep health endpoint performing database connectivity check."""
    ready = await check_db_ready()
    if not ready:
        raise HTTPException(status_code=HTTP_503_SERVICE_UNAVAILABLE, detail="Not ready")
    return {"status": "ready"}


@router.get("/ready", status_code=HTTP_200_OK)
async def ready() -> dict:
    """Alias for deep readiness to match deployment health checks."""
    ready = await check_db_ready()
    if not ready:
        raise HTTPException(status_code=HTTP_503_SERVICE_UNAVAILABLE, detail="Not ready")
    return {"status": "ready"}
