import asyncio
from datetime import datetime, timezone

import pytest

from app.db.session import Base
from app.db.repositories.external_token_repository import ExternalTokenRepository
from app.db.models import Tenant
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession


@pytest.mark.asyncio
async def test_external_token_persistence():
    """Integration-style test isolated to a local sqlite async engine.

    This test uses a dedicated `sqlite+aiosqlite` engine to avoid
    mixing the project's global asyncpg engine with test-time
    synchronous helpers, which can attach futures to different
    event loops and cause intermittent failures.
    """
    test_db_url = "sqlite+aiosqlite:///./.test_integration_sqlite.db"
    engine_local = create_async_engine(test_db_url, future=True, echo=False)
    AsyncSessionLocal = async_sessionmaker(bind=engine_local, class_=AsyncSession, expire_on_commit=False)

    # Import models to ensure Base metadata includes latest columns
    import app.db.models  # noqa: F401

    # Create schema on the local engine. Drop existing tables first to avoid
    # stale file-backed DBs that may have older schema versions.
    async with engine_local.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    try:
        async with AsyncSessionLocal() as db:
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
    finally:
        await engine_local.dispose()
