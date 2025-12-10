# app/db/repositories/notification_repository.py
"""
CRUD operations for Notification model.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.models import Notification
from uuid import UUID
from typing import Optional, List

class NotificationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, tenant_id: UUID, flow_id: str, event_id: UUID, channel: str, message: str, status: str) -> Notification:
        notification = Notification(
            tenant_id=tenant_id,
            flow_id=flow_id,
            event_id=event_id,
            channel=channel,
            message=message,
            status=status
        )
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)
        return notification

    async def get(self, notification_id: UUID) -> Optional[Notification]:
        result = await self.db.execute(select(Notification).where(Notification.id == notification_id))
        return result.scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: UUID) -> List[Notification]:
        result = await self.db.execute(select(Notification).where(Notification.tenant_id == tenant_id))
        return result.scalars().all()

    async def update(self, notification_id: UUID, **kwargs) -> Optional[Notification]:
        notification = await self.get(notification_id)
        if not notification:
            return None
        for key, value in kwargs.items():
            setattr(notification, key, value)
        await self.db.commit()
        await self.db.refresh(notification)
        return notification

    async def delete(self, notification_id: UUID) -> bool:
        notification = await self.get(notification_id)
        if not notification:
            return False
        await self.db.delete(notification)
        await self.db.commit()
        return True
