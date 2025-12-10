# app/db/repositories/raw_event_repository.py
"""
CRUD operations for RawEvent model.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.models import RawEvent
from uuid import UUID
from typing import Optional, List

class RawEventRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, tenant_id: UUID, flow_id: str, source: str, payload: dict, idempotency_key: str) -> RawEvent:
        event = RawEvent(
            tenant_id=tenant_id,
            flow_id=flow_id,
            source=source,
            payload=payload,
            idempotency_key=idempotency_key
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def get(self, event_id: UUID) -> Optional[RawEvent]:
        result = await self.db.execute(select(RawEvent).where(RawEvent.id == event_id))
        return result.scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: UUID) -> List[RawEvent]:
        result = await self.db.execute(select(RawEvent).where(RawEvent.tenant_id == tenant_id))
        return result.scalars().all()

    async def update(self, event_id: UUID, **kwargs) -> Optional[RawEvent]:
        event = await self.get(event_id)
        if not event:
            return None
        for key, value in kwargs.items():
            setattr(event, key, value)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def delete(self, event_id: UUID) -> bool:
        event = await self.get(event_id)
        if not event:
            return False
        await self.db.delete(event)
        await self.db.commit()
        return True
