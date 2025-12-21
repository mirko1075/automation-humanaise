"""
ingestors/imap/repository.py

Persistence and deduplication for IMAP ingestor. Stores raw events and
ensures idempotency by tenant_id + mailbox + uid + uidvalidity.
"""
from __future__ import annotations

from typing import Optional
from datetime import datetime
import os
import structlog

from sqlalchemy import Column, Integer, String, DateTime, LargeBinary, JSON, UniqueConstraint, create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import IntegrityError

from app.db.session import Base

logger = structlog.get_logger()


class IMAPRawEvent(Base):
    __tablename__ = 'imap_raw_events'
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, nullable=False, index=True)
    mailbox = Column(String, nullable=False)
    uid = Column(Integer, nullable=False)
    uidvalidity = Column(String, nullable=False)
    message_id = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    received_at = Column(DateTime, nullable=False)
    raw = Column(LargeBinary, nullable=False)
    event_metadata = Column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint('tenant_id', 'mailbox', 'uid', 'uidvalidity', name='uq_imap_uid'),
    )


class IMAPRepository:
    """Repository to persist and deduplicate IMAP raw events.

    This implementation uses a synchronous SQLAlchemy engine created from
    the environment `DATABASE_URL` (async suffix removed if present). This
    keeps the ingestor synchronous and simple while persisting to the same
    Postgres database.
    """

    def __init__(self, database_url: Optional[str] = None):
        dsn = database_url or os.environ.get('DATABASE_URL')
        if not dsn:
            raise RuntimeError('DATABASE_URL is required for IMAPRepository')
        sync_dsn = dsn.replace('+asyncpg', '')
        self.engine = create_engine(sync_dsn)
        self.Session = sessionmaker(bind=self.engine)

    def exists(self, tenant_id: str, mailbox: str, uid: int, uidvalidity: str) -> bool:
        with self.Session() as s:
            return s.query(IMAPRawEvent).filter_by(
                tenant_id=tenant_id, mailbox=mailbox, uid=uid, uidvalidity=uidvalidity
            ).first() is not None

    def persist_raw(self, tenant_id: str, mailbox: str, uid: int, uidvalidity: str, raw: bytes, metadata: dict) -> Optional[int]:
        with self.Session() as s:
            evt = IMAPRawEvent(
                tenant_id=tenant_id,
                mailbox=mailbox,
                uid=uid,
                uidvalidity=uidvalidity,
                message_id=metadata.get('message_id'),
                subject=metadata.get('subject'),
                received_at=datetime.utcnow(),
                raw=raw,
                event_metadata=metadata,
            )
            s.add(evt)
            try:
                s.commit()
                s.refresh(evt)
                logger.info("imap_event_persisted", tenant_id=tenant_id, uid=uid, id=evt.id)
                return evt.id
            except IntegrityError:
                s.rollback()
                logger.info("imap_event_duplicate", tenant_id=tenant_id, uid=uid)
                return None

    def record_error(self, tenant_id: Optional[str], component: str, function: str, message: str, details: Optional[dict] = None, severity: str = "ERROR"):
        """Persist a synchronous error log entry to `error_logs` table.

        This is a best-effort helper used by sync ingestors to ensure
        errors are auditable when async audit helpers are not available.
        """
        try:
            # Import here to avoid circular imports at module import time
            from app.db.models import ErrorLog
            with self.Session() as s:
                el = ErrorLog(
                    request_id=None,
                    tenant_id=tenant_id,
                    flow_id=None,
                    component=component,
                    function=function,
                    severity=severity,
                    message=message,
                    details=details,
                )
                s.add(el)
                try:
                    s.commit()
                except Exception:
                    s.rollback()
        except Exception:
            # Never raise from error logging
            logger.exception("failed_to_record_error_log")

