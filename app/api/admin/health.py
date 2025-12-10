# app/api/admin/health.py
"""
HealthCheckSuite for Edilcos Automation Backend.
Provides /health and /health/deep endpoints.
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.monitoring.logger import log
from app.monitoring.audit import audit_event
from app.monitoring.slack_alerts import send_slack_alert
from app.db.session import SessionLocal
from app.integrations.gmail_api import fetch_message
from app.integrations.onedrive_api import get_graph_client
from app.config import settings
import traceback

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/health")
async def health():
    log("INFO", "Health shallow check", module="health")
    return {"status": "ok", "version": "1.0.0"}

@router.get("/health/deep")
async def health_deep(request: Request):
    request_id = getattr(request.state, "request_id", None)
    components = {}
    status = "ok"
    try:
        # DB check
        try:
            async with SessionLocal() as db:
                await db.execute("SELECT 1")
            components["db"] = "ok"
        except Exception:
            components["db"] = "error"
            status = "degraded"
        # Gmail check (config only)
        if settings.GMAIL_CREDENTIALS_PATH:
            components["gmail"] = "configured"
        else:
            components["gmail"] = "missing"
            status = "degraded"
        # OneDrive check (config only)
        if settings.ONEDRIVE_CLIENT_ID and settings.ONEDRIVE_CLIENT_SECRET:
            components["onedrive"] = "configured"
        else:
            components["onedrive"] = "missing"
            status = "degraded"
        # WhatsApp check (config only)
        if settings.WHATSAPP_API_TOKEN:
            components["whatsapp"] = "configured"
        else:
            components["whatsapp"] = "missing"
            status = "degraded"
        # Scheduler check (app.state.scheduler)
        scheduler_status = getattr(request.app.state, "scheduler", None)
        components["scheduler"] = "running" if scheduler_status else "not_running"
        if not scheduler_status:
            status = "degraded"
        log("INFO", f"Health deep check: {components}", module="health", request_id=request_id)
        await audit_event("health_deep_checked", None, None, {"components": components, "status": status}, request_id=request_id)
        if status == "degraded":
            log("WARNING", f"Health degraded: {components}", module="health", request_id=request_id)
        return {"status": status, "components": components}
    except Exception as exc:
        tb = traceback.format_exc()
        log("ERROR", f"Health deep check error: {exc}", module="health", request_id=request_id)
        await audit_event("health_deep_error", None, None, {"error": str(exc), "traceback": tb}, request_id=request_id)
        await send_slack_alert(f"Health deep check error: {exc}", context={"traceback": tb}, severity="CRITICAL", module="health", request_id=request_id)
        return JSONResponse(status_code=500, content={"status": "error", "components": components})
