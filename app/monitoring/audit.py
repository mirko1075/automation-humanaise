# app/monitoring/audit.py
"""
Audit logging for Edilcos Automation Backend.
"""
from app.db.models import AuditLog
from app.db.session import SessionLocal
from datetime import datetime
from uuid import uuid4
from typing import Any, Dict

async def audit_event(event_type: str, tenant_id: str, flow_id: str, payload: Dict[str, Any], actor: str = None, request_id: str = None):
    async with SessionLocal() as session:
        audit_log = AuditLog(
            id=uuid4(),
            event_type=event_type,
            tenant_id=tenant_id,
            flow_id=flow_id,
            details=payload,
            actor=actor,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        session.add(audit_log)
        await session.commit()
