# app/db/repositories/normalized_event_repository.py
"""
CRUD operations for NormalizedEvent model.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.models import NormalizedEvent
from uuid import UUID
from typing import Optional, List

class NormalizedEventRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, tenant_id: UUID, flow_id: str, event_type: str, normalized_data: dict, status: str) -> NormalizedEvent:
        event = NormalizedEvent(
            tenant_id=tenant_id,
            flow_id=flow_id,
            event_type=event_type,
            normalized_data=normalized_data,
            status=status
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def get(self, event_id: UUID) -> Optional[NormalizedEvent]:
        result = await self.db.execute(select(NormalizedEvent).where(NormalizedEvent.id == event_id))
        return result.scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: UUID) -> List[NormalizedEvent]:
        result = await self.db.execute(select(NormalizedEvent).where(NormalizedEvent.tenant_id == tenant_id))
        return result.scalars().all()

    async def update(self, event_id: UUID, **kwargs) -> Optional[NormalizedEvent]:
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
