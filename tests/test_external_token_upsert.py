import pytest
from app.db.session import Base
from app.db.models import Tenant
from app.db.repositories.external_token_repository import ExternalTokenRepository
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession




@pytest.mark.asyncio
async def test_upsert_creates_and_updates():
    # Use an isolated local SQLite async engine for this test to avoid
    # cross-loop asyncpg connection issues in CI/local envs that set
    # DATABASE_URL to a Postgres database.
    test_db_url = "sqlite+aiosqlite:///./.test_sqlite.db"
    engine_local = create_async_engine(test_db_url, future=True, echo=False)
    AsyncSessionLocal = async_sessionmaker(bind=engine_local, class_=AsyncSession, expire_on_commit=False)

    # Ensure models are imported so metadata includes all columns
    import app.db.models  # noqa: F401

    # Create tables on the local engine. Drop existing tables first to avoid
    # stale file-backed DBs that may have older schema versions.
    async with engine_local.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        tenant = Tenant(name="upsert-tenant")
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)

        repo = ExternalTokenRepository(db)

        # First upsert should create
        row = await repo.upsert(tenant_id=tenant.id, flow_id=None, provider="google", token="first", external_id="u@example.com", data={"expires_in": 10})
        assert row is not None
        assert row.token == "first"

        # Second upsert with new token should update existing row
        row2 = await repo.upsert(tenant_id=tenant.id, flow_id=None, provider="google", token="second", external_id="u@example.com", data={"expires_in": 20})
        assert row2 is not None
        assert row2.token == "second"
