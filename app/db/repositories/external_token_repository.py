# app/db/repositories/external_token_repository.py
"""
CRUD operations for ExternalToken model.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.models import ExternalToken
from uuid import UUID
from typing import Optional, List

class ExternalTokenRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, tenant_id: UUID, flow_id: str, service: str, token: str) -> ExternalToken:
        ext_token = ExternalToken(
            tenant_id=tenant_id,
            flow_id=flow_id,
            service=service,
            token=token
        )
        self.db.add(ext_token)
        await self.db.commit()
        await self.db.refresh(ext_token)
        return ext_token

    async def get(self, token_id: UUID) -> Optional[ExternalToken]:
        result = await self.db.execute(select(ExternalToken).where(ExternalToken.id == token_id))
        return result.scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: UUID) -> List[ExternalToken]:
        result = await self.db.execute(select(ExternalToken).where(ExternalToken.tenant_id == tenant_id))
        return result.scalars().all()

    async def list_by_external_id(self, external_id: str) -> List[ExternalToken]:
        result = await self.db.execute(select(ExternalToken).where(ExternalToken.external_id == external_id))
        return result.scalars().all()

    async def update(self, token_id: UUID, **kwargs) -> Optional[ExternalToken]:
        ext_token = await self.get(token_id)
        if not ext_token:
            return None
        for key, value in kwargs.items():
            setattr(ext_token, key, value)
        await self.db.commit()
        await self.db.refresh(ext_token)
        return ext_token

    async def delete(self, token_id: UUID) -> bool:
        ext_token = await self.get(token_id)
        if not ext_token:
            return False
        await self.db.delete(ext_token)
        await self.db.commit()
        return True
