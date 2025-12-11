from app.db.models import ErrorLog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4
from datetime import datetime


class ErrorRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, *, request_id=None, tenant_id=None, flow_id=None, component=None, function=None, severity="ERROR", message="", details=None, stacktrace=None):
        el = ErrorLog(
            id=uuid4(),
            request_id=request_id,
            tenant_id=tenant_id,
            flow_id=flow_id,
            component=component,
            function=function,
            severity=severity,
            message=message,
            details=details,
            stacktrace=stacktrace,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.db.add(el)
        await self.db.commit()
        await self.db.refresh(el)
        return el

    async def list_by_tenant(self, tenant_id, limit=100, offset=0):
        q = await self.db.execute(select(ErrorLog).where(ErrorLog.tenant_id == tenant_id).limit(limit).offset(offset))
        return q.scalars().all()

    async def list_all(self, limit=100, offset=0):
        q = await self.db.execute(select(ErrorLog).limit(limit).offset(offset))
        return q.scalars().all()
