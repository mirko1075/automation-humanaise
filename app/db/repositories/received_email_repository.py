"""
app/db/repositories/received_email_repository.py

Repository for storing incoming received emails (ingest-only webhook log).
"""
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import ReceivedEmail
from uuid import UUID
from typing import Optional


class ReceivedEmailRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        tenant_id: Optional[UUID],
        channel: str,
        identifier: Optional[str],
        external_ref: Optional[str],
        raw_payload: dict,
        outcome: str = "received",
    ) -> ReceivedEmail:
        rec = ReceivedEmail(
            tenant_id=tenant_id,
            channel=channel,
            identifier=identifier,
            external_ref=external_ref,
            outcome=outcome,
            processed=False,
            raw_payload=raw_payload,
        )
        self.db.add(rec)
        await self.db.commit()
        await self.db.refresh(rec)
        return rec
