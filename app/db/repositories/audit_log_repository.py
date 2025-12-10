# app/db/repositories/audit_log_repository.py
"""
CRUD operations for AuditLog model.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.models import AuditLog
from uuid import UUID
from typing import Optional, List

class AuditLogRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, tenant_id: UUID, flow_id: str, action: str, actor: str = None, details: dict = None) -> AuditLog:
        audit_log = AuditLog(
            tenant_id=tenant_id,
            flow_id=flow_id,
            action=action,
            actor=actor,
            details=details
        )
        self.db.add(audit_log)
        await self.db.commit()
        await self.db.refresh(audit_log)
        return audit_log

    async def get(self, log_id: UUID) -> Optional[AuditLog]:
        result = await self.db.execute(select(AuditLog).where(AuditLog.id == log_id))
        return result.scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: UUID) -> List[AuditLog]:
        result = await self.db.execute(select(AuditLog).where(AuditLog.tenant_id == tenant_id))
        return result.scalars().all()

    async def update(self, log_id: UUID, **kwargs) -> Optional[AuditLog]:
        audit_log = await self.get(log_id)
        if not audit_log:
            return None
        for key, value in kwargs.items():
            setattr(audit_log, key, value)
        await self.db.commit()
        await self.db.refresh(audit_log)
        return audit_log

    async def delete(self, log_id: UUID) -> bool:
        audit_log = await self.get(log_id)
        if not audit_log:
            return False
        await self.db.delete(audit_log)
        await self.db.commit()
        return True
