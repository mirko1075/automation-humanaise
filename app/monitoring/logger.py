# app/monitoring/logger.py
"""
Structured JSON logger for Edilcos Automation Backend.
"""
import logging
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
def get_request_context():
    # Import lazily to avoid import cycles
    from app.monitoring.context import get_request_context as _g
    return _g()

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "component": getattr(record, "component", record.module),
            "request_id": getattr(record, "request_id", None),
            "tenant_id": str(getattr(record, "tenant_id", None)) if getattr(record, "tenant_id", None) is not None else None,
            "flow_id": str(getattr(record, "flow_id", None)) if getattr(record, "flow_id", None) is not None else None,
        }
        return json.dumps(log_record)

logger = logging.getLogger("edilcos")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.handlers = [handler]

# Keys reserved by LogRecord that must not be passed in `extra`
_LOGRECORD_RESERVED = set(vars(logging.LogRecord("n", 0, "", 0, "", (), None)).keys())

# Helper to log with context
def log(level: str, message: str, component: str = None, request_id: str = None, tenant_id: str = None, flow_id: str = None, **kwargs):
    # Map legacy 'module' kwarg to 'component' to avoid LogRecord collision
    if "module" in kwargs and not component:
        component = kwargs.pop("module")
    # Fill missing fields from contextvars
    ctx = get_request_context()
    if request_id is None:
        request_id = ctx.get("request_id")
    if tenant_id is None:
        tenant_id = ctx.get("tenant_id")
    if flow_id is None:
        flow_id = ctx.get("flow_id")

    extra = {
        "request_id": request_id,
        "tenant_id": tenant_id,
        "flow_id": flow_id,
        "component": component,
        **{k: v for k, v in kwargs.items() if k not in _LOGRECORD_RESERVED}
    }
    logger.log(getattr(logging, level.upper(), logging.INFO), message, extra=extra)

# TODO(monitoring): expose metric raw_event_processing_latency_seconds histogram
# TODO(monitoring): expose gauge in_flight_normalizations
# TODO(alerting): alert on error rate spikes for normalizer/dispatcher
