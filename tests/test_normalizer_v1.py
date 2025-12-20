import asyncio
from datetime import datetime
from uuid import uuid4

import pytest

from app.db.session import SessionLocal, ensure_tables_async
from app.db.models import Tenant, RawEvent, Customer, Quote, ReceivedEmail
from app.core.normalizer.service import normalize_raw_event


@pytest.mark.asyncio
async def test_normalize_raw_event_new_quote():
    # Ensure tables exist
    create_tables = ensure_tables_async()
    await create_tables()

    async with SessionLocal() as session:
        async with session.begin():
            # Create a tenant
            tenant_id = uuid4()
            await session.execute(
                Tenant.__table__.insert().values(id=tenant_id, name='test', contact_channels={'email': []}, created_at=datetime.utcnow(), updated_at=datetime.utcnow())
            )

            # Create a RawEvent that will be classified as new_quote
            raw_id = uuid4()
            payload = {
                "parsed": {
                    "from_email": "cliente@example.com",
                    "subject": "Richiesta preventivo ristrutturazione",
                    "body_text": "Vorrei un preventivo",
                }
            }

            await session.execute(
                RawEvent.__table__.insert().values(
                    id=raw_id,
                    tenant_id=tenant_id,
                    flow_id='preventivi_v1',
                    source='gmail',
                    payload=payload,
                    idempotency_key=str(raw_id),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )

    # Run normalization
    dto = await normalize_raw_event(raw_id)
    assert dto is not None
    assert dto.outcome in {"new_quote", "follow_up", "unassigned", "ignored"}

    # Verify DB side-effects
    async with SessionLocal() as session:
        async with session.begin():
            res = await session.execute(ReceivedEmail.__table__.select().where(ReceivedEmail.external_ref == str(raw_id)))
            rec = res.first()
            assert rec is not None

            # If new_quote, verify Quote and Customer exist
            if dto.outcome == "new_quote":
                res_c = await session.execute(Customer.__table__.select().where(Customer.email == 'cliente@example.com'))
                c = res_c.first()
                assert c is not None

                res_q = await session.execute(Quote.__table__.select().where(Quote.tenant_id == dto.tenant_id))
                q = res_q.first()
                assert q is not None

    # Idempotency: second run does nothing (returns None)
    dto2 = await normalize_raw_event(raw_id)
    assert dto2 is None
