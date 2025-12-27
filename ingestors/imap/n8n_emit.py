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
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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

    # Use a session with retries for idempotent/connection-failure scenarios
    session = requests.Session()
    # Retry on connection errors and 5xx server responses; do NOT retry on 4xx (e.g. 404)
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("POST",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    try:
        logger.debug("Emitting to N8N", extra={"message_uid": uid, "tenant_id": tenant})
        resp = session.post(webhook_url, json=envelope, timeout=5)

        # If 4xx (client) error, surface clear log and do not retry
        if 400 <= resp.status_code < 500:
            response_snippet = f"n8n returned {resp.status_code} for url {webhook_url}: {resp.text[:200]}"
            logger.error("n8n_emit_client_error", extra={"status_code": resp.status_code, "tenant_id": tenant, "event_id": event_id, "uid": uid, "response_snippet": response_snippet})
            if resp.status_code == 404:
                logger.error("n8n_emit_404_hint", extra={"hint": "Verify the configured N8N webhook path and that the workflow is active."})
            logger.warning("n8n_emit_failed", extra={"status_code": resp.status_code, "tenant_id": tenant, "event_id": event_id, "uid": uid})
            return

        # For other statuses, raise for status to trigger retries if configured
        try:
            resp.raise_for_status()
        except requests.HTTPError as he:
            logger.exception("n8n_emit_http_error", extra={"error": str(he), "status_code": getattr(resp, 'status_code', None), "tenant_id": tenant, "event_id": event_id, "uid": uid})
            logger.warning("n8n_emit_failed", extra={"error": str(he), "tenant_id": tenant, "event_id": event_id, "uid": uid})
            return

        logger.info("n8n_emit_ok", extra={"tenant_id": tenant, "event_id": event_id, "uid": uid})
    except Exception as e:
        # Network/connectivity errors etc.
        logger.exception("Exception during emit_to_n8n", extra={"error": str(e), "tenant_id": tenant, "event_id": event_id, "uid": uid})
        logger.warning("n8n_emit_failed", extra={"error": str(e), "tenant_id": tenant, "event_id": event_id, "uid": uid})
    finally:
        try:
            session.close()
        except Exception:
            pass
