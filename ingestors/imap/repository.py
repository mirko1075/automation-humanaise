"""
ingestors/imap/repository.py

Repository for IMAP ingestor persistence.
Provides deduplication and raw message storage.
"""
from typing import Any, Dict, Optional
from venv import logger
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.models import RawEmail  # Assumes RawEmail model exists with tenant_id and external_id/message_id fields

class IMAPRepository:
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url)

    def exists_external_id(self, tenant_id: str, external_id: str) -> bool:
        """
        Check if a message with the given external_id exists for the tenant.

        Args:
            tenant_id: Tenant identifier.
            external_id: External message identifier (e.g., message_id).

        Returns:
            True if exists, False otherwise.
        """
        with Session(self.engine) as session:
            stmt = select(RawEmail).where(
                RawEmail.tenant_id == tenant_id,
                RawEmail.external_id == external_id
            )
            return session.execute(stmt).first() is not None

    def persist_raw_message(self, tenant_id: str, raw_email: Any, metadata: Dict[str, Any]) -> None:
        """
        Persist the raw email message.

        Args:
            tenant_id: Tenant identifier.
            raw_email: Raw email object.
            metadata: Metadata dictionary.
        """
        with Session(self.engine) as session:
            email = RawEmail(
                tenant_id=tenant_id,
                external_id=metadata.get("message_id"),
                raw_content=raw_email.raw_bytes,
                metadata=metadata,
            )
            session.add(email)
            session.commit()
            session.refresh(email)
            
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

