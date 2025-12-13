"""
Tests for admin monitoring endpoints: filters and audit trail retrieval.
"""
from uuid import uuid4
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.main import app
from app.db.models import RawEvent, NormalizedEvent, AuditLog, Tenant
from app.db.session import SessionLocal, engine, Base


@pytest_asyncio.fixture
async def client():
    from httpx import AsyncClient as AC, ASGITransport

    transport = ASGITransport(app=app)
    async with AC(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session():
    # Ensure tables exist when running tests with SQLite by creating schema
    try:
        if str(engine.url).startswith("sqlite"):
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)
    except Exception:
        pass

    async with SessionLocal() as db:
        yield db


@pytest_asyncio.fixture
async def test_tenant(db_session):
    tenant = Tenant(id=uuid4(), name="Monitor Tenant", status="active", active_flows=["preventivi_v1"])
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest.mark.asyncio
async def test_raw_events_filters_and_audit_trail(db_session, test_tenant, client: AsyncClient):
    # Insert sample RawEvent with event_type in payload
    key1 = f"msg-{uuid4()}"
    key2 = f"msg-{uuid4()}"

    rv1 = RawEvent(
        id=uuid4(),
        tenant_id=test_tenant.id,
        source="gmail",
        payload={"event_type": "new_quote", "subject": "Preventivo demo"},
        processed=True,
        idempotency_key=key1,
    )
    rv2 = RawEvent(
        id=uuid4(),
        tenant_id=test_tenant.id,
        source="gmail",
        payload={"event_type": "other_event", "subject": "Altro"},
        processed=False,
        idempotency_key=key2,
    )

    db_session.add_all([rv1, rv2])

    # Insert normalized events
    ne = NormalizedEvent(
        id=uuid4(),
        tenant_id=test_tenant.id,
        flow_id="preventivi_v1",
        event_type="new_quote",
        normalized_data={"customer": "Demo"},
        status="processed",
    )
    db_session.add(ne)

    # Insert audit logs referencing idempotency key
    a1 = AuditLog(
        id=uuid4(),
        tenant_id=test_tenant.id,
        flow_id="preventivi_v1",
        action="preventivi_discarded",
        details={"reason": "test", "idempotency_key": key1},
    )
    a2 = AuditLog(
        id=uuid4(),
        tenant_id=test_tenant.id,
        flow_id="preventivi_v1",
        action="preventivi_discarded",
        details={"reason": "other", "idempotency_key": key2},
    )
    db_session.add_all([a1, a2])
    await db_session.commit()

    # Test raw_events filter by event_type
    resp = await client.get(f"/admin/monitoring/raw_events?tenant_id={test_tenant.id}&event_type=new_quote&limit=10")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "success"
    assert any(r["idempotency_key"] == key1 for r in data["data"])

    # Test normalized_events filter by event_type
    resp2 = await client.get(f"/admin/monitoring/normalized_events?tenant_id={test_tenant.id}&event_type=new_quote&limit=10")
    assert resp2.status_code == 200, resp2.text
    data2 = resp2.json()
    assert data2["status"] == "success"
    assert any(n["event_type"] == "new_quote" for n in data2["data"])

    # Test discarded_audits tenant filter
    resp3 = await client.get(f"/admin/monitoring/discarded_audits?tenant_id={test_tenant.id}&limit=10")
    assert resp3.status_code == 200, resp3.text
    data3 = resp3.json()
    assert data3["status"] == "success"
    assert any(a["details"]["idempotency_key"] == key1 for a in data3["data"])

    # Test audit_trail for specific idempotency_key
    resp4 = await client.get(f"/admin/monitoring/audit_trail?idempotency_key={key1}")
    assert resp4.status_code == 200, resp4.text
    data4 = resp4.json()
    assert data4["status"] == "success"
    assert all(key1 in (a["details"].get("idempotency_key") or "") for a in data4["data"])


@pytest.mark.asyncio
async def test_date_range_and_invalid_format(db_session, test_tenant, client: AsyncClient):
    # Create events on specific dates
    now = datetime.utcnow()
    older = now - timedelta(days=10)
    newer = now + timedelta(days=1)

    old_key = f"msg-{uuid4()}"
    new_key = f"msg-{uuid4()}"
    r_old = RawEvent(id=uuid4(), tenant_id=test_tenant.id, source="gmail", payload={"event_type": "dr"}, processed=True, idempotency_key=old_key, created_at=older)
    r_new = RawEvent(id=uuid4(), tenant_id=test_tenant.id, source="gmail", payload={"event_type": "dr"}, processed=True, idempotency_key=new_key, created_at=newer)
    db_session.add_all([r_old, r_new])
    await db_session.commit()

    # Query with a date range that includes only older
    start = (older - timedelta(seconds=1)).isoformat()
    end = (older + timedelta(seconds=1)).isoformat()
    resp = await client.get(f"/admin/monitoring/raw_events?tenant_id={test_tenant.id}&start_date={start}&end_date={end}")
    assert resp.status_code == 200
    data = resp.json()
    assert any(r["idempotency_key"] == old_key for r in data["data"])

    # Invalid date format should return 400
    resp_bad = await client.get(f"/admin/monitoring/raw_events?start_date=not-a-date")
    assert resp_bad.status_code == 400


@pytest.mark.asyncio
async def test_nested_event_type_search(db_session, test_tenant, client: AsyncClient):
    # Event_type inside nested payload path
    nested_key = f"msg-{uuid4()}"
    nested = RawEvent(id=uuid4(), tenant_id=test_tenant.id, source="gmail", payload={"normalized": {"event_type": "nested_quote"}}, processed=True, idempotency_key=nested_key)
    # Also create a normalized event with event_type
    ne2 = NormalizedEvent(id=uuid4(), tenant_id=test_tenant.id, flow_id="preventivi_v1", event_type="nested_quote", normalized_data={"info": 1}, status="processed")
    db_session.add_all([nested, ne2])
    await db_session.commit()

    # Our current raw_events filter only checks payload->>'event_type', so this nested one won't match.
    resp = await client.get(f"/admin/monitoring/raw_events?tenant_id={test_tenant.id}&event_type=nested_quote")
    assert resp.status_code == 200
    data = resp.json()
    assert all(r["idempotency_key"] != nested_key for r in data["data"])  # nested not returned

    # But normalized_events filter should return the normalized event
    resp2 = await client.get(f"/admin/monitoring/normalized_events?tenant_id={test_tenant.id}&event_type=nested_quote")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert any(n["event_type"] == "nested_quote" for n in data2["data"])

