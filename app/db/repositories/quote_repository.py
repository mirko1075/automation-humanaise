# app/db/repositories/quote_repository.py
"""
CRUD operations for Quote model.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.models import Quote
from uuid import UUID
from typing import Optional, List

class QuoteRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, tenant_id: UUID, flow_id: str, customer_id: UUID, quote_data: dict, status: str, pdf_url: str = None) -> Quote:
        quote = Quote(
            tenant_id=tenant_id,
            flow_id=flow_id,
            customer_id=customer_id,
            quote_data=quote_data,
            status=status,
            pdf_url=pdf_url
        )
        self.db.add(quote)
        await self.db.commit()
        await self.db.refresh(quote)
        return quote

    async def get(self, quote_id: UUID) -> Optional[Quote]:
        result = await self.db.execute(select(Quote).where(Quote.id == quote_id))
        return result.scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: UUID) -> List[Quote]:
        result = await self.db.execute(select(Quote).where(Quote.tenant_id == tenant_id))
        return result.scalars().all()

    async def update(self, quote_id: UUID, **kwargs) -> Optional[Quote]:
        quote = await self.get(quote_id)
        if not quote:
            return None
        for key, value in kwargs.items():
            setattr(quote, key, value)
        await self.db.commit()
        await self.db.refresh(quote)
        return quote

    async def delete(self, quote_id: UUID) -> bool:
        quote = await self.get(quote_id)
        if not quote:
            return False
        await self.db.delete(quote)
        await self.db.commit()
        return True
