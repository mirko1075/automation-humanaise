import asyncio
from uuid import uuid4
from datetime import datetime
from httpx import AsyncClient, ASGITransport
from app.main import app
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from app.db.session import Base
from app.db.models import Tenant, RawEvent

async def main():
    db_file = '/tmp/test_debug_db.sqlite'
    url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_async_engine(url, future=True, echo=True)
    TestSessionLocal = sessionmaker(bind=engine, class_=__import__('sqlalchemy.ext.asyncio').ext.asyncio.AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with TestSessionLocal() as session:
        tenant = Tenant(id=uuid4(), name='T', status='active')
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)
        key1 = f"msg-{uuid4()}"
        rv1 = RawEvent(id=uuid4(), tenant_id=tenant.id, source='gmail', payload={'event_type':'new_quote'}, processed=True, idempotency_key=key1)
        rv2 = RawEvent(id=uuid4(), tenant_id=tenant.id, source='gmail', payload={'event_type':'other_event'}, processed=False, idempotency_key=f"msg-{uuid4()}")
        session.add_all([rv1, rv2])
        await session.commit()
    # override dependency
    from app.db.session import get_async_session as real_dep
    async def _get_test_session():
        async with TestSessionLocal() as s:
            yield s
    app.dependency_overrides.clear()
    app.dependency_overrides[real_dep] = _get_test_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://testserver') as client:
        resp = await client.get(f"/admin/monitoring/raw_events?tenant_id={tenant.id}&event_type=new_quote&limit=10")
        print('STATUS', resp.status_code)
        print(resp.text)

if __name__ == '__main__':
    asyncio.run(main())
