"""
Integration-style tests for QuoteRepository state validation.

This uses the project's `db_session` pytest-asyncio fixture to obtain an
`AsyncSession` compatible with repository classes.
"""
import pytest
import pytest_asyncio
from uuid import uuid4

from app.db.repositories.quote_repository import QuoteRepository
from app.db.models import Quote
from app.core.preventivo_state import PreventivoStatus


@pytest_asyncio.fixture
async def db_session(tmp_path):
    """Create a dedicated SQLite async engine for this test file and yield a session."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.db.session import Base

    db_file = tmp_path / "test_db.sqlite"
    test_url = f"sqlite+aiosqlite:///{db_file}"
    test_engine = create_async_engine(test_url, future=True, echo=False)
    TestSessionLocal = sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    # Ensure models are imported
    import app.db.models  # noqa: F401

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_quote_repository_rejects_invalid_transition(db_session):
    # Arrange: create a quote with terminal status WON
    qid = uuid4()
    quote = Quote(
        id=qid,
        tenant_id=uuid4(),
        flow_id="preventivi_v1",
        customer_id=uuid4(),
        quote_data={"demo": True},
        status=PreventivoStatus.WON.value,
    )
    db_session.add(quote)
    await db_session.commit()
    await db_session.refresh(quote)

    repo = QuoteRepository(db_session)

    # Act / Assert: attempt to change status from WON -> IN_PROGRESS should raise ValueError
    with pytest.raises(ValueError):
        await repo.update(qid, status=PreventivoStatus.IN_PROGRESS.value)

    # Cleanup: ensure the status remained unchanged
    q_after = await repo.get(qid)
    assert q_after.status == PreventivoStatus.WON.value
