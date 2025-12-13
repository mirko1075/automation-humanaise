import asyncio
from datetime import datetime, timezone

import pytest

from app.db.session import engine, SessionLocal, Base
from app.db.repositories.external_token_repository import ExternalTokenRepository
from app.db.models import Tenant


@pytest.mark.asyncio
async def test_external_token_persistence():
    # Create tables if using SQLite in-memory
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        # Create a tenant first to satisfy FK constraint
        t = Tenant(name="integration-tenant")
        db.add(t)
        await db.commit()
        await db.refresh(t)

        repo = ExternalTokenRepository(db)
        token = await repo.create(
            tenant_id=t.id,
            flow_id=None,
            provider="google",
            token="ya29.test",
            external_id="user@example.com",
            data={"expires_in": 3600}
        )

        assert token is not None
        assert str(token.tenant_id) == str(t.id)
        assert token.provider == "google"
        assert token.external_id == "user@example.com"
