"""
ingestors/imap/poller.py

Polling orchestration for IMAP ingestor. This module performs:
- connect to IMAP
- select mailbox
- find UIDs since last processed
- fetch, parse, and persist

This is intentionally simple and synchronous.
"""
from __future__ import annotations

import os
import time
import logging
from typing import Optional

from .imap_client import IMAPClient
from .parser import parse_rfc822
from .repository import IMAPRepository
from app.config import settings

logger = logging.getLogger("ingestors.imap.poller")


class IMAPPoller:
    def __init__(self, tenant_id: str, mailbox: str = "INBOX", interval_seconds: int = 60):
        self.tenant_id = tenant_id
        self.mailbox = mailbox
        self.interval = int(os.environ.get('IMAP_POLL_INTERVAL', str(interval_seconds)))
        self.client = IMAPClient()

    def run_once(self):
        """Run one poll cycle: connect, select mailbox, fetch new UIDs, process each."""
        try:
            self.client.connect()
        except Exception as e:
            logger.exception("imap_connect_failed")
            # Persist error and return
            try:
                repo = IMAPRepository(database_url=settings.DATABASE_URL)
                repo.record_error(self.tenant_id, component='imap_client', function='connect', message=str(e), details={})
            except Exception:
                logger.exception("failed_recording_connect_error")
            return

        try:
            msg_count, uidvalidity = self.client.select_mailbox(self.mailbox)
        except Exception as e:
            logger.exception("imap_select_failed", mailbox=self.mailbox)
            try:
                repo = IMAPRepository(database_url=settings.DATABASE_URL)
                repo.record_error(self.tenant_id, component='imap_client', function='select_mailbox', message=str(e), details={'mailbox': self.mailbox})
            except Exception:
                logger.exception("failed_recording_select_error")
            return
        logger.info("mailbox_selected", mailbox=self.mailbox, message_count=msg_count, uidvalidity=uidvalidity)

        # Determine last processed UID from DB
        repo = IMAPRepository(database_url=settings.DATABASE_URL)
        # Find max uid processed for this tenant/mailbox/uidvalidity
        with repo.engine.connect() as conn:
            r = conn.execute(
                "SELECT MAX(uid) FROM imap_raw_events WHERE tenant_id=:t AND mailbox=:m AND uidvalidity=:u",
                {"t": self.tenant_id, "m": self.mailbox, "u": uidvalidity},
            )
            row = r.scalar()
        last_uid = int(row) if row is not None else None
        logger.info("last_uid", tenant_id=self.tenant_id, mailbox=self.mailbox, last_uid=last_uid)

        uids = self.client.fetch_uids_since(last_uid)
        logger.info("uids_fetched", count=len(uids), uids=uids)

        for uid in uids:
            try:
                raw, meta = self.client.fetch_message_by_uid(uid)
            except Exception as e:
                logger.exception("imap_fetch_failed", uid=uid)
                try:
                    repo.record_error(self.tenant_id, component='imap_client', function='fetch_message_by_uid', message=str(e), details={'uid': uid})
                except Exception:
                    logger.exception("failed_recording_fetch_error")
                continue
            # Quick dedupe check by repository
                if repo.exists(self.tenant_id, self.mailbox, uid, uidvalidity):
                    logger.info("skip_duplicate", tenant_id=self.tenant_id, uid=uid)
                    continue
                # parse
                parsed = parse_rfc822(raw, tenant_id=self.tenant_id, mailbox=self.mailbox, uid=uid, uidvalidity=uidvalidity)
                # Persist raw event and metadata
                metadata = {
                    'message_id': parsed.message_id,
                    'subject': parsed.subject,
                    'from': parsed.from_,
                    'to': parsed.to,
                }
                repo.persist_raw(self.tenant_id, self.mailbox, uid, uidvalidity, raw, metadata)
                logger.info("email_ingested", tenant_id=self.tenant_id, uid=uid)
            except Exception:
                logger.exception("process_uid_failed", uid=uid)

    def run_forever(self):
        logger.info("imap_poller_start", tenant_id=self.tenant_id, mailbox=self.mailbox, interval=self.interval)
        try:
            while True:
                self.run_once()
                time.sleep(self.interval)
        finally:
            self.client.logout()
