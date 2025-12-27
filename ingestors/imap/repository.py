"""
ingestors/imap/repository.py

Repository for IMAP ingestor persistence.
Provides deduplication and raw message storage.
"""
from typing import Any, Dict, Optional
import json
import logging
from sqlalchemy import create_engine, select, Column, Integer, String, LargeBinary, JSON, DateTime
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session, declarative_base
from sqlalchemy.sql import func

logger = logging.getLogger(__name__)

Base = declarative_base()


class IMAPRawEvent(Base):
    __tablename__ = "imap_raw_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, index=True, nullable=True)
    mailbox = Column(String, nullable=True)
    # `uid` can come from different providers. For IMAP it is an integer,
    # but Graph returns opaque string ids. Use String to be provider-agnostic.
    uid = Column(String, nullable=True)
    uidvalidity = Column(String, nullable=True)
    message_id = Column(String, index=True, nullable=True)
    raw = Column(LargeBinary, nullable=True)
    # Historically the Alembic migration created the column `event_metadata`.
    # Map the Python attribute `metadata_json` to that DB column name so the
    # model matches the existing schema and avoids undefined-column errors.
    metadata_json = Column("event_metadata", JSON, nullable=True)
    # Store original inbound payload (JSON/JSONB). Nullable and optional.
    raw_payload = Column(JSON, nullable=True)
    # The migration created a `received_at` timestamp column; map our
    # `created_at` attribute to that column name for compatibility.
    created_at = Column("received_at", DateTime, server_default=func.now())


class IMAPRepository:
    def __init__(self, database_url: str):
        # If the configured URL uses an async driver (eg. 'postgresql+asyncpg'),
        # coerce it to a sync driver by stripping the async fragment before
        # creating the engine. This prevents SQLAlchemy from creating an async
        # dialect that later raises `MissingGreenlet` when used synchronously.
        try:
            url_obj = make_url(database_url)
            if "+asyncpg" in url_obj.drivername:
                coerced_url = database_url.replace("+asyncpg", "")
                logger.debug("coercing async DB URL to sync by removing +asyncpg")
                self.engine = create_engine(coerced_url)
                logger.info("created sync engine from async DB URL by coercion")
            else:
                self.engine = create_engine(database_url)
        except Exception:
            logger.exception("failed to create SQLAlchemy engine for IMAPRepository")
            raise
        # Ensure local tables exist for this repository when used with a test sqlite DB
        try:
            Base.metadata.create_all(bind=self.engine)
        except Exception:
            logger.debug("Could not create local IMAP tables; assuming they exist")

    def exists_external_id(self, tenant_id: str, external_id: str) -> bool:
        """
        Check if a message with the given external_id exists for the tenant.
        """
        with Session(self.engine) as session:
            stmt = select(IMAPRawEvent).where(
                IMAPRawEvent.tenant_id == tenant_id,
                IMAPRawEvent.message_id == external_id,
            )
            return session.execute(stmt).first() is not None

    def persist_raw(self, tenant_id: str, mailbox: str, uid: str | int, uidvalidity: str, raw_bytes: bytes, metadata: Dict[str, Any], raw_payload: Optional[dict] = None) -> Optional[int]:
        """
        Persist a raw IMAP message. Returns the inserted row id, or None if duplicate.
        """
        message_id = metadata.get("message_id") if isinstance(metadata, dict) else None
        if message_id and self.exists_external_id(tenant_id, message_id):
            return None

        # Ensure raw_payload is JSON-serializable; if not, persist as NULL
        payload_to_store = None
        if isinstance(raw_payload, dict):
            try:
                # quick check for serializability
                json.dumps(raw_payload)
                payload_to_store = raw_payload
            except Exception:
                payload_to_store = None

        with Session(self.engine) as session:
            event = IMAPRawEvent(
                tenant_id=tenant_id,
                mailbox=mailbox,
                uid=uid,
                uidvalidity=uidvalidity,
                message_id=message_id,
                raw=raw_bytes,
                metadata_json=metadata,
                raw_payload=payload_to_store,
            )
            session.add(event)
            session.commit()
            session.refresh(event)
            return int(event.id)

    def persist_raw_message(self, tenant_id: str, raw_email: Any, metadata: Dict[str, Any]) -> None:
        """
        Backwards-compatible method used by poller: accepts a RawEmail dataclass-like object.
        """
        raw_bytes = getattr(raw_email, "raw_bytes", None) or getattr(raw_email, "text", None) or b""
        mailbox = getattr(raw_email, "mailbox", None) or "INBOX"
        uid = getattr(raw_email, "uid", None) or ""
        uidvalidity = getattr(raw_email, "uidvalidity", None) or ""
        # Use persist_raw which handles dedup; pass through raw_payload if present
        raw_payload = getattr(raw_email, "raw_payload", None)
        try:
            self.persist_raw(tenant_id, mailbox, uid, uidvalidity, raw_bytes, metadata, raw_payload=raw_payload)
        except Exception:
            # Do not let raw_payload serialization issues break ingestion
            try:
                self.persist_raw(tenant_id, mailbox, uid, uidvalidity, raw_bytes, metadata, raw_payload=None)
            except Exception:
                # bubble up the underlying DB error
                raise
            
    def record_error(
        self,
        tenant_id: Optional[str],
        component: str,
        function: str,
        message: str,
        details: Optional[dict] = None,
        severity: str = "ERROR",
        flow_id: Optional[str] = None,
    ) -> None:
        """
        Persist a synchronous error log entry to `error_logs` table.

        Args:
            tenant_id: Tenant identifier.
            component: Component name.
            function: Function name.
            message: Error message.
            details: Optional error details.
            severity: Log severity.
            flow_id: Flow identifier (optional).

        Returns:
            None
        """
        import structlog
        logger = structlog.get_logger()
        try:
            from app.db.models import ErrorLog
            with Session(self.engine) as session:
                el = ErrorLog(
                    request_id=None,
                    tenant_id=tenant_id,
                    flow_id=flow_id,
                    component=component,
                    function=function,
                    severity=severity,
                    message=message,
                    details=details,
                )
                session.add(el)
                try:
                    session.commit()
                except Exception:
                    session.rollback()
        except Exception:
            logger.exception("failed_to_record_error_log", tenant_id=tenant_id, component=component, function=function)

