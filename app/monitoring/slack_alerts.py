# app/monitoring/slack_alerts.py
"""
Slack alerting for Edilcos Automation Backend.
"""
import httpx
from app.config import settings
from app.monitoring.logger import log
from typing import Optional, Dict
import os

async def send_slack_alert(message: str, context: Optional[Dict] = None, severity: str = "ERROR", module: str = None, request_id: str = None):
    webhook_url = settings.SLACK_WEBHOOK_URL
    if not webhook_url:
        log("WARNING", "Slack webhook URL not configured", module=module, request_id=request_id)
        return
    env = os.getenv("ENVIRONMENT", "development")
    payload = {
        "text": f"[{env}] [{severity}] [{module}] {message}\nRequest ID: {request_id}\nContext: {context or {}}"
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(webhook_url, json=payload, timeout=5)
    except Exception as e:
        log("ERROR", f"Failed to send Slack alert: {e}", module=module, request_id=request_id)
