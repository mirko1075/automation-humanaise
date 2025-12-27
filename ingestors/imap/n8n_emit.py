# ingestors/imap/n8n_emit.py
"""
Helper to emit InboundMessage to n8n via webhook.
"""
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any
import requests
import structlog
from app.config import settings

logger = structlog.get_logger()

def emit_to_n8n(inbound_message: Dict[str, Any]) -> None:
    """
    Emit an InboundMessage to n8n via HTTP POST webhook.

    Args:
        inbound_message: The InboundMessage dict to emit.
    """
    webhook_url = os.getenv("N8N_WEBHOOK_URL") or getattr(settings, "N8N_WEBHOOK_URL", None)
    if not webhook_url:
        print("EXCEPTION", "No N8N webhook URL configured")
        logger.warning("n8n_emit_failed", reason="no_webhook_url", event_id=inbound_message.get("id"), tenant_id=inbound_message.get("source", {}).get("account_id"), uid=inbound_message.get("source", {}).get("message_uid"))
        return
    event_id = str(uuid.uuid4())
    envelope = {
        "event_type": "inbound_message.received",
        "event_id": event_id,
        "emitted_at": datetime.now(timezone.utc).isoformat(),
        "payload": inbound_message,
    }
    try:
        print("EMITTING TO N8N", inbound_message.get("source", {}).get("message_uid"))
        resp = requests.post(webhook_url, json=envelope, timeout=5)
        resp.raise_for_status()
        logger.info(
            "n8n_emit_ok",
            tenant_id=inbound_message.get("source", {}).get("account_id"),
            event_id=event_id,
            uid=inbound_message.get("source", {}).get("message_uid"),
        )
    except Exception as e:
        print("EXCEPTION", e)
        logger.warning(
            "n8n_emit_failed",
            error=str(e),
            tenant_id=inbound_message.get("source", {}).get("account_id"),
            event_id=event_id,
            uid=inbound_message.get("source", {}).get("message_uid"),
        )
