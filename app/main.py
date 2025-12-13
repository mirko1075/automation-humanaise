# app/main.py
"""
Main FastAPI app with monitoring integration and health endpoints.
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4
import traceback

from app.monitoring.logger import log
from app.monitoring.audit import audit_event
from app.monitoring.slack_alerts import send_slack_alert
from app.monitoring.context import set_request_context
from app.api.admin.health import router as health_router
from app.api.admin.errors import router as errors_router
from app.api.ingress.gmail_webhook import router as gmail_router
from app.api.admin.monitoring import router as monitoring_router

app = FastAPI(title="Edilcos Automation Backend")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid4())
    request.state.request_id = request_id
    set_request_context(request_id=request_id)
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
        action="exception",
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

# Mount routers
app.include_router(health_router)
app.include_router(errors_router)
app.include_router(gmail_router)
app.include_router(monitoring_router)

# Logging initialization
log("INFO", "Edilcos Automation Backend started", module="main")
