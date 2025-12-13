# app/db/repositories/integration_event_repository.py
"""
Repository for IntegrationEvent model.
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import IntegrationEvent
from datetime import datetime

class IntegrationEventRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        integration: str,
        event_type: str,
        level: str,
        message: str,
        context: Optional[dict] = None,
    ) -> IntegrationEvent:
        ie = IntegrationEvent(
            integration=integration,
            event_type=event_type,
            level=level,
            message=message,
            context=context or {},
        )
        self.db.add(ie)
        await self.db.commit()
        await self.db.refresh(ie)
        return ie

    async def list(
        self,
        integration: Optional[str] = None,
        level: Optional[str] = None,
        event_type: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[IntegrationEvent]:
        stmt = select(IntegrationEvent)
        if integration:
            stmt = stmt.where(IntegrationEvent.integration == integration)
        if level:
            stmt = stmt.where(IntegrationEvent.level == level)
        if event_type:
            stmt = stmt.where(IntegrationEvent.event_type == event_type)
        if since:
            stmt = stmt.where(IntegrationEvent.created_at >= since)
        stmt = stmt.order_by(IntegrationEvent.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return result.scalars().all()
