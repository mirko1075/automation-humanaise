# app/db/repositories/tenant_repository.py
"""
CRUD operations for Tenant model.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.models import Tenant
from uuid import UUID
from typing import Optional, List

class TenantRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, name: str) -> Tenant:
        tenant = Tenant(name=name)
        self.db.add(tenant)
        await self.db.commit()
        await self.db.refresh(tenant)
        return tenant

    async def get(self, tenant_id: UUID) -> Optional[Tenant]:
        result = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
        return result.scalar_one_or_none()

    async def list(self) -> List[Tenant]:
        result = await self.db.execute(select(Tenant))
        return result.scalars().all()

    async def update(self, tenant_id: UUID, **kwargs) -> Optional[Tenant]:
        tenant = await self.get(tenant_id)
        if not tenant:
            return None
        for key, value in kwargs.items():
            setattr(tenant, key, value)
        await self.db.commit()
        await self.db.refresh(tenant)
        return tenant

    async def delete(self, tenant_id: UUID) -> bool:
        tenant = await self.get(tenant_id)
        if not tenant:
            return False
        await self.db.delete(tenant)
        await self.db.commit()
        return True
