# app/main.py
"""
Main FastAPI app with monitoring integration.
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from uuid import uuid4
from app.monitoring.logger import log
from app.monitoring.audit import audit_event
from app.monitoring.slack_alerts import send_slack_alert
import traceback
from app.api.ingress.gmail_webhook import router as gmail_router

app = FastAPI()

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    tb = traceback.format_exc()
    log(
        "ERROR",
        f"Unhandled exception: {exc}",
        module="main",
        request_id=request_id
    )
    await audit_event(
        event_type="exception",
        tenant_id=None,
        flow_id=None,
        payload={"error": str(exc), "traceback": tb},
        request_id=request_id
    )
    await send_slack_alert(
        message=f"Critical error: {exc}",
        context={"traceback": tb},
        severity="CRITICAL",
        module="main",
        request_id=request_id
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "request_id": request_id,
            "detail": "An unexpected error occurred."
        }
    )

app.include_router(gmail_router)

# Logging initialization
log("INFO", "Edilcos Automation Backend started", module="main")

# ...existing code for routers, startup, etc...
