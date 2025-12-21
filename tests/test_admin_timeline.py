import asyncio
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from uuid import uuid4

from app.main import app
from app.db.models import AuditLog


@pytest_asyncio.fixture
async def db_session(tmp_path):
    """Create a dedicated SQLite async engine for this test and yield an AsyncSession.

    Also override FastAPI dependency `get_async_session` to use this test session.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.db.session import Base

    db_file = tmp_path / "test_db_timeline.sqlite"
    test_url = f"sqlite+aiosqlite:///{db_file}"
    test_engine = create_async_engine(test_url, future=True, echo=False)
    TestSessionLocal = sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    # Ensure models are imported
    import app.db.models  # noqa: F401

    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        # Override FastAPI dependency to use this test session
        from app.main import app as _app
        from app.db.session import get_async_session as real_dep

        async def _get_test_session():
            async with TestSessionLocal() as s:
                yield s

        _app.dependency_overrides.clear()
        _app.dependency_overrides[real_dep] = _get_test_session

        yield session

    await test_engine.dispose()


# Use the shared async `client` fixture provided in tests/test_monitoring_endpoints.py
# which overrides FastAPI dependencies and provides an AsyncClient.


@pytest.mark.asyncio
async def test_timeline_search_pagination(db_session):
    # Insert sample audit logs
    now = datetime.utcnow()
    items = []
    for i in range(1, 21):
        a = AuditLog(
            action="test.action" if i % 2 == 0 else "other.action",
            tenant_id=uuid4(),
            flow_id="flow_x",
            details={"raw_event_id": f"raw_{i}", "request_id": f"req_{i}"},
            created_at=now - timedelta(minutes=i),
        )
        db_session.add(a)
        items.append(a)
    await db_session.commit()

    from httpx import AsyncClient as AC, ASGITransport

    transport = ASGITransport(app=app)
    async with AC(transport=transport, base_url="http://testserver") as ac:
        # page 1, per_page 5
        resp = await ac.get("/admin/timeline/search", params={"page": 1, "per_page": 5})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "success"
        data = payload["data"]
        assert data["page"] == 1
        assert data["per_page"] == 5
        assert data["total"] == 20
        assert len(data["items"]) == 5

        # Filter by action
        resp2 = await ac.get("/admin/timeline/search", params={"action": "test.action", "per_page": 100})
        assert resp2.status_code == 200
        payload2 = resp2.json()
        assert payload2["status"] == "success"
        assert payload2["data"]["total"] == 10

        # Date range filter
        from_ts = (now - timedelta(minutes=15)).isoformat()
        to_ts = (now - timedelta(minutes=5)).isoformat()
        resp3 = await ac.get("/admin/timeline/search", params={"from_ts": from_ts, "to_ts": to_ts, "per_page": 100})
        assert resp3.status_code == 200
        payload3 = resp3.json()
        assert payload3["status"] == "success"
        # should include items with created_at between the range
        assert payload3["data"]["total"] > 0
