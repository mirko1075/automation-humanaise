import pytest
import asyncio
from types import SimpleNamespace
from uuid import uuid4, UUID

from app.db.session import SessionLocal
from app.db.models import Customer, Quote, ReceivedEmail, Tenant


@pytest.mark.asyncio
async def test_dispatch_new_quote_happy_path():
    from app.core import dispatcher

    tenant_id = UUID(int=1)
    raw_event_id = uuid4()

    normalized = {
        "customer": {"name": "Mario Rossi", "email": "mario@example.com"},
        "quote": {"items": [{"desc": "Lavori bagno", "qty": 1, "price": 1000}]},
    }

    event = SimpleNamespace(
        outcome="new_quote",
        normalized_data=normalized,
        raw_event_id=str(raw_event_id),
        tenant_id=tenant_id,
        flow_id="preventivi_v1",
    )

    async with SessionLocal() as db:
        # ensure tenant exists to satisfy FK constraints (idempotent)
        res = await db.execute(Tenant.__table__.select().where(Tenant.id == tenant_id))
        if res.first() is None:
            await db.execute(Tenant.__table__.insert().values(id=tenant_id, name="test", status="active"))
            await db.commit()
        # cleanup any prior state for this tenant (test DB may be shared)
        await db.execute(Quote.__table__.delete().where(Quote.tenant_id == tenant_id))
        await db.execute(ReceivedEmail.__table__.delete().where(ReceivedEmail.tenant_id == tenant_id))
        await db.commit()

    async with SessionLocal() as db:
        await dispatcher.dispatch(event, db)
        await db.commit()

        # Assert customer created
        result = await db.execute(
            Customer.__table__.select().where(Customer.email == "mario@example.com")
        )
        cust_row = result.first()
        assert cust_row is not None

        # Assert quote created once
        qres = await db.execute(Quote.__table__.select().where(Quote.tenant_id == tenant_id))
        quotes = qres.fetchall()
        assert len(quotes) == 1

        # Assert received email log created
        rres = await db.execute(ReceivedEmail.__table__.select().where(ReceivedEmail.external_ref == str(raw_event_id)))
        rows = rres.fetchall()
        assert len(rows) == 1


@pytest.mark.asyncio
async def test_dispatch_follow_up_appends_mail_only():
    from app.core import dispatcher

    tenant_id = UUID(int=2)
    raw_event_id = uuid4()

    normalized = {
        "customer": {"name": "Luigi Bianchi", "email": "luigi@example.com"},
        "quote": {},
    }

    event = SimpleNamespace(
        outcome="follow_up",
        normalized_data=normalized,
        raw_event_id=str(raw_event_id),
        tenant_id=tenant_id,
        flow_id="preventivi_v1",
    )

    async with SessionLocal() as db:
        # ensure tenant exists and pre-create a customer/quote (idempotent)
        tres = await db.execute(Tenant.__table__.select().where(Tenant.id == tenant_id))
        if tres.first() is None:
            await db.execute(Tenant.__table__.insert().values(id=tenant_id, name="t2", status="active"))
            await db.commit()
        # cleanup any prior state for this tenant
        await db.execute(Quote.__table__.delete().where(Quote.tenant_id == tenant_id))
        await db.execute(ReceivedEmail.__table__.delete().where(ReceivedEmail.tenant_id == tenant_id))
        await db.commit()
        await db.execute(
            Customer.__table__.insert().values(
                id=uuid4(), tenant_id=tenant_id, flow_id="preventivi_v1", name="Luigi Bianchi", email="luigi@example.com"
            )
        )
        await db.commit()

    async with SessionLocal() as db:
        await dispatcher.dispatch(event, db)
        await db.commit()

        # No new quotes should be created for this follow_up dispatch
        qres = await db.execute(Quote.__table__.select().where(Quote.tenant_id == tenant_id))
        quotes = qres.fetchall()
        assert len(quotes) == 0

        # Received email log should be present
        rres = await db.execute(ReceivedEmail.__table__.select().where(ReceivedEmail.external_ref == str(raw_event_id)))
        rows = rres.fetchall()
        assert len(rows) == 1


@pytest.mark.asyncio
async def test_dispatch_ignored_and_unassigned_do_nothing():
    from app.core import dispatcher

    tenant_id = UUID(int=3)
    raw_event_id = uuid4()

    normalized = {"customer": {}, "quote": {}}

    for outcome in ["ignored", "unassigned"]:
        event = SimpleNamespace(
            outcome=outcome,
            normalized_data=normalized,
            raw_event_id=str(raw_event_id),
            tenant_id=tenant_id,
            flow_id="preventivi_v1",
        )

        async with SessionLocal() as db:
            tres = await db.execute(Tenant.__table__.select().where(Tenant.id == tenant_id))
            if tres.first() is None:
                await db.execute(Tenant.__table__.insert().values(id=tenant_id, name="t3", status="active"))
                await db.commit()
            # cleanup any prior state for this tenant
            await db.execute(Quote.__table__.delete().where(Quote.tenant_id == tenant_id))
            await db.execute(ReceivedEmail.__table__.delete().where(ReceivedEmail.tenant_id == tenant_id))
            await db.commit()

        async with SessionLocal() as db:
            await dispatcher.dispatch(event, db)
            await db.commit()

            # No quotes created
            qres = await db.execute(Quote.__table__.select().where(Quote.tenant_id == tenant_id))
            quotes = qres.fetchall()
            assert len(quotes) == 0

            # No received email log for these outcomes
            rres = await db.execute(ReceivedEmail.__table__.select().where(ReceivedEmail.external_ref == str(raw_event_id)))
            rows = rres.fetchall()
            assert len(rows) == 0


@pytest.mark.asyncio
async def test_dispatch_new_quote_idempotent():
    from app.core import dispatcher

    tenant_id = UUID(int=4)
    raw_event_id = uuid4()

    normalized = {
        "customer": {"name": "Anna Verdi", "email": "anna@example.com"},
        "quote": {"items": [{"desc": "Pavimento", "qty": 10, "price": 20}]},
    }

    event = SimpleNamespace(
        outcome="new_quote",
        normalized_data=normalized,
        raw_event_id=str(raw_event_id),
        tenant_id=tenant_id,
        flow_id="preventivi_v1",
    )

    async with SessionLocal() as db:
        tres = await db.execute(Tenant.__table__.select().where(Tenant.id == tenant_id))
        if tres.first() is None:
            await db.execute(Tenant.__table__.insert().values(id=tenant_id, name="t4", status="active"))
            await db.commit()
        # cleanup any prior state for this tenant
        await db.execute(Quote.__table__.delete().where(Quote.tenant_id == tenant_id))
        await db.execute(ReceivedEmail.__table__.delete().where(ReceivedEmail.tenant_id == tenant_id))
        await db.commit()

    async with SessionLocal() as db:
        # First dispatch
        await dispatcher.dispatch(event, db)
        await db.commit()

    async with SessionLocal() as db:
        # Second dispatch should not create duplicate
        await dispatcher.dispatch(event, db)
        await db.commit()

        qres = await db.execute(Quote.__table__.select().where(Quote.tenant_id == tenant_id))
        quotes = qres.fetchall()
        assert len(quotes) == 1
