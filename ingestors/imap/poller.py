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
from typing import Optional

from ingestors.mail.base_client import BaseMailClient
from .parser import parse_rfc822
from .repository import IMAPRepository
from .adapter import rawemail_to_inbound
from .n8n_emit import emit_to_n8n
from app.config import settings

import structlog

logger = structlog.get_logger("ingestors.imap.poller")


class MailPoller:
    """
    Provider-agnostic poller for mail ingestion.
    """

    def __init__(
        self,
        tenant_id: str,
        mail_client: BaseMailClient,
        interval_seconds: int = 60,
    ):
        self.tenant_id = tenant_id
        self.client = mail_client
        self.interval = interval_seconds

    def run_once(self):
        logger.info("poll_cycle_start", tenant_id=self.tenant_id)
        try:
            self.client.connect()
        except Exception as e:
            logger.exception("mail_client_connect_failed", tenant_id=self.tenant_id)
            return

        repo = IMAPRepository(database_url=settings.DATABASE_URL)

        for raw in self.client.fetch_messages():
            try:
                # Deduplicate by message_id (external_id)
                if raw.message_id is None:
                    logger.warning("skip_message_missing_id", tenant_id=self.tenant_id)
                    continue
                if repo.exists_external_id(self.tenant_id, raw.message_id):
                    logger.info("skip_duplicate", tenant_id=self.tenant_id, external_id=raw.message_id)
                    continue

                metadata = {
                    "message_id": raw.message_id,
                    "subject": raw.subject,
                    "from": raw.from_,
                    "to": raw.to,
                }

                repo.persist_raw_message(
                    tenant_id=self.tenant_id,
                    raw_email=raw,
                    metadata=metadata,
                )

                inbound = rawemail_to_inbound(raw)
                try:
                    emit_to_n8n(inbound)
                except Exception:
                    logger.exception("emit_to_n8n_failed", tenant_id=self.tenant_id, message_id=raw.message_id)

                logger.info("email_ingested", tenant_id=self.tenant_id, message_id=raw.message_id)

            except Exception:
                logger.exception("process_message_failed", tenant_id=self.tenant_id, message_id=getattr(raw, "message_id", None))

        self.client.disconnect()

    def run_forever(self):
        logger.info(
            "mail_poller_start",
            tenant_id=self.tenant_id,
            interval=self.interval,
        )
        try:
            while True:
                self.run_once()
                time.sleep(self.interval)
        finally:
            self.client.disconnect()
