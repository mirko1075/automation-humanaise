# app/db/repositories/customer_repository.py
"""
CRUD operations for Customer model.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.models import Customer
from uuid import UUID
from typing import Optional, List

class CustomerRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, tenant_id: UUID, flow_id: str, name: str, email: str = None, phone: str = None) -> Customer:
        customer = Customer(
            tenant_id=tenant_id,
            flow_id=flow_id,
            name=name,
            email=email,
            phone=phone
        )
        self.db.add(customer)
        await self.db.commit()
        await self.db.refresh(customer)
        return customer

    async def get(self, customer_id: UUID) -> Optional[Customer]:
        result = await self.db.execute(select(Customer).where(Customer.id == customer_id))
        return result.scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: UUID) -> List[Customer]:
        result = await self.db.execute(select(Customer).where(Customer.tenant_id == tenant_id))
        return result.scalars().all()

    async def update(self, customer_id: UUID, **kwargs) -> Optional[Customer]:
        customer = await self.get(customer_id)
        if not customer:
            return None
        for key, value in kwargs.items():
            setattr(customer, key, value)
        await self.db.commit()
        await self.db.refresh(customer)
        return customer

    async def delete(self, customer_id: UUID) -> bool:
        customer = await self.get(customer_id)
        if not customer:
            return False
        await self.db.delete(customer)
        await self.db.commit()
        return True
