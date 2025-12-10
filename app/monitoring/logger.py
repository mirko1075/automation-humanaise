# app/monitoring/logger.py
"""
Structured JSON logger for Edilcos Automation Backend.
"""
import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "request_id": getattr(record, "request_id", None),
            "tenant_id": getattr(record, "tenant_id", None),
            "flow_id": getattr(record, "flow_id", None),
        }
        return json.dumps(log_record)

logger = logging.getLogger("edilcos")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.handlers = [handler]

# Helper to log with context
def log(level: str, message: str, module: str = None, request_id: str = None, tenant_id: str = None, flow_id: str = None, **kwargs):
    extra = {
        "request_id": request_id,
        "tenant_id": tenant_id,
        "flow_id": flow_id,
        "module": module,
        **kwargs
    }
    logger.log(getattr(logging, level.upper(), logging.INFO), message, extra=extra)
