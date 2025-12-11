# app/monitoring/audit.py
"""
Audit logging for Edilcos Automation Backend.
"""
from app.db.models import AuditLog
from app.db.session import SessionLocal
from datetime import datetime
from uuid import uuid4
from typing import Any, Dict, Optional
from app.monitoring.logger import log


async def audit_event(action: str, tenant_id: Optional[str], flow_id: Optional[str], payload: Dict[str, Any], actor: Optional[str] = None, request_id: Optional[str] = None):
    """Persist an audit log entry in a fail-safe way.

    action: a short action name (e.g. 'quote_created')
    tenant_id / flow_id may be None.
    This helper never raises: on DB errors it logs locally and returns.
    """
    try:
        async with SessionLocal() as session:
            audit_log = AuditLog(
                id=uuid4(),
                tenant_id=tenant_id,
                flow_id=flow_id,
                action=action,
                actor=actor,
                details=payload,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(audit_log)
            await session.commit()
    except Exception as e:
        # Fail-safe: log locally and do not raise
        log("ERROR", f"Failed to write audit_event {action}: {e}", component="audit", request_id=request_id, tenant_id=tenant_id, flow_id=flow_id)
