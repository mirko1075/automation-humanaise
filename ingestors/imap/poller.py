"""
ingestors/imap/poller.py

Polling orchestration for mail ingestor (provider-agnostic).
Performs:
- connect to mail provider
- fetch, parse, and persist messages
- deduplicate by message_id
- emit to n8n

This is intentionally simple and synchronous.
"""
from __future__ import annotations

import time
import logging
import os
if not logging.getLogger().hasHandlers():
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
from typing import Optional

from ingestors.mail.base_client import BaseMailClient
from .repository import IMAPRepository
from .adapter import rawemail_to_inbound
from .n8n_emit import emit_to_n8n
from app.config import settings

logger = logging.getLogger(__name__)


class MailPoller:
    """Provider-agnostic poller for mail ingestion.

    Uses only the BaseMailClient API (`connect`, `fetch_messages`, `disconnect`).
    Deduplicates by `RawEmail.message_id`, persists raw messages, and emits to n8n.
    """

    def __init__(
        self,
        tenant_id: str,
        mail_client: BaseMailClient,
        interval_seconds: int = 60,
    ) -> None:
        self.tenant_id = tenant_id
        self.client = mail_client
        self.interval = interval_seconds
        self.provider = getattr(mail_client.__class__, "__name__", "unknown")

    def run_once(self) -> None:
        logger.debug("poll_cycle_start", extra={"tenant_id": self.tenant_id, "provider": self.provider})

        try:
            logger.debug("Connecting to mail provider", extra={"tenant_id": self.tenant_id, "provider": self.provider})
            self.client.connect()
            logger.debug("Connected to mail provider", extra={"tenant_id": self.tenant_id, "provider": self.provider})
        except Exception:
            logger.exception("mail_client_connect_failed", extra={"tenant_id": self.tenant_id, "provider": self.provider})
            return

        repo = IMAPRepository(database_url=settings.DATABASE_URL)

        try:
            messages = list(self.client.fetch_messages())
            logger.debug("Fetched messages", extra={"tenant_id": self.tenant_id, "provider": self.provider, "count": len(messages)})
        except Exception:
            logger.exception("mail_fetch_failed", extra={"tenant_id": self.tenant_id, "provider": self.provider})
            try:
                self.client.disconnect()
            except Exception:
                logger.exception("mail_client_disconnect_failed", extra={"tenant_id": self.tenant_id, "provider": self.provider})
            return

        for raw in messages:
            logger.debug("Processing message", extra={"tenant_id": self.tenant_id, "provider": self.provider, "message_id": getattr(raw, "message_id", None)})
            try:
                # Skip messages without canonical external id
                if getattr(raw, "message_id", None) is None:
                    logger.debug("Skipping message with missing message_id", extra={"tenant_id": self.tenant_id, "provider": self.provider})
                    continue

                # Deduplication
                if repo.exists_external_id(self.tenant_id, raw.message_id or ""):
                    logger.info("skip_duplicate", extra={"tenant_id": self.tenant_id, "provider": self.provider, "external_id": raw.message_id})
                    logger.debug("Deduplication: message already exists, skipping", extra={"tenant_id": self.tenant_id, "provider": self.provider, "message_id": raw.message_id})
                    continue

                metadata = {
                    "message_id": raw.message_id,
                    "subject": getattr(raw, "subject", None),
                    "from": getattr(raw, "from_", None),
                    "to": getattr(raw, "to", None),
                }

                logger.debug("Persisting raw message", extra={"tenant_id": self.tenant_id, "provider": self.provider, "message_id": raw.message_id})
                try:
                    repo.persist_raw_message(tenant_id=self.tenant_id, raw_email=raw, metadata=metadata)
                    logger.debug("Persisted raw message", extra={"tenant_id": self.tenant_id, "provider": self.provider, "message_id": raw.message_id})
                except Exception:
                    logger.exception("persist_raw_message_failed", extra={"tenant_id": self.tenant_id, "provider": self.provider, "message_id": raw.message_id})
                    # continue processing other messages
                    continue

                inbound = rawemail_to_inbound(raw)
                logger.debug("Emitting to n8n", extra={"tenant_id": self.tenant_id, "provider": self.provider, "message_id": raw.message_id})
                try:
                    emit_to_n8n(inbound)
                    logger.info("email_ingested", extra={"tenant_id": self.tenant_id, "provider": self.provider, "message_id": raw.message_id})
                    logger.debug("Successfully emitted to n8n", extra={"tenant_id": self.tenant_id, "provider": self.provider, "message_id": raw.message_id})
                except Exception:
                    logger.exception("emit_to_n8n_failed", extra={"tenant_id": self.tenant_id, "provider": self.provider, "message_id": raw.message_id})

            except Exception:
                logger.exception("process_message_failed", extra={"tenant_id": self.tenant_id, "provider": self.provider, "message_id": getattr(raw, "message_id", None)})

        try:
            self.client.disconnect()
            logger.debug("Disconnected from mail provider", extra={"tenant_id": self.tenant_id, "provider": self.provider})
        except Exception:
            logger.exception("mail_client_disconnect_failed", extra={"tenant_id": self.tenant_id, "provider": self.provider})

    def run_forever(self) -> None:
        logger.info("mail_poller_start", extra={"tenant_id": self.tenant_id, "interval": self.interval, "provider": self.provider})
        try:
            while True:
                logger.debug("Starting poller cycle", extra={"tenant_id": self.tenant_id, "provider": self.provider})
                self.run_once()
                logger.debug("Sleeping before next poller cycle", extra={"tenant_id": self.tenant_id, "provider": self.provider, "interval": self.interval})
                time.sleep(self.interval)
        finally:
            try:
                self.client.disconnect()
            except Exception:
                logger.exception("mail_client_disconnect_failed", extra={"tenant_id": self.tenant_id, "provider": self.provider})
            logger.info("mail_poller_stopped", extra={"tenant_id": self.tenant_id, "provider": self.provider})
