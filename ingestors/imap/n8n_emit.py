# ingestors/imap/n8n_emit.py
"""
ingestors/imap/n8n_emit.py

Emit an InboundMessage to n8n via HTTP POST webhook.

Uses standard Python logging and respects the central logging configuration.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any
import logging
import requests

from app.config import settings
from app.logging import configure_logging

# Ensure logging configured for standalone module imports
configure_logging()
logger = logging.getLogger(__name__)


def emit_to_n8n(inbound_message: Dict[str, Any]) -> None:
    """
    Emit an InboundMessage to n8n via HTTP POST webhook.

    Args:
        inbound_message: The InboundMessage dict to emit.
    """
    webhook_url = os.getenv("N8N_WEBHOOK_URL") or getattr(settings, "N8N_WEBHOOK_URL", None)
    if not webhook_url:
        logger.error("No N8N webhook URL configured", extra={"tenant_id": inbound_message.get("source", {}).get("account_id"), "uid": inbound_message.get("source", {}).get("message_uid")})
        logger.warning("n8n_emit_failed", extra={"reason": "no_webhook_url", "event_id": inbound_message.get("id"), "tenant_id": inbound_message.get("source", {}).get("account_id"), "uid": inbound_message.get("source", {}).get("message_uid")})
        return

    event_id = str(uuid.uuid4())
    envelope = {
        "event_type": "inbound_message.received",
        "event_id": event_id,
        "emitted_at": datetime.now(timezone.utc).isoformat(),
        "payload": inbound_message,
    }

    uid = inbound_message.get("source", {}).get("message_uid")
    tenant = inbound_message.get("source", {}).get("account_id")

    try:
        logger.debug("Emitting to N8N", extra={"message_uid": uid, "tenant_id": tenant})
        resp = requests.post(webhook_url, json=envelope, timeout=5)
        resp.raise_for_status()
        logger.info("n8n_emit_ok", extra={"tenant_id": tenant, "event_id": event_id, "uid": uid})
    except Exception as e:
        logger.exception("Exception during emit_to_n8n", extra={"error": str(e), "tenant_id": tenant, "event_id": event_id, "uid": uid})
        logger.warning("n8n_emit_failed", extra={"error": str(e), "tenant_id": tenant, "event_id": event_id, "uid": uid})
