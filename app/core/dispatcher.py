"""
app/core/dispatcher.py

Dispatcher V1: DB-only side effects for Preventivi flow.

Functions:
  async def dispatch(event: NormalizedEvent-like, db) -> None

Rules:
  - For outcome 'new_quote': upsert customer, create quote, insert received email log
  - For outcome 'follow_up': append received email log only
  - For 'ignored'|'unassigned': do nothing

Idempotency:
  - Use ReceivedEmail.external_ref == event.raw_event_id to check prior processing

Note: This module DOES NOT commit the session. Caller controls transactions.
"""
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from typing import Any

from sqlalchemy import select
from app.db.models import Customer, Quote, ReceivedEmail


async def dispatch(event: Any, db) -> None:
    """Dispatch DB side-effects for a NormalizedEvent-like object.

    Args:
        event: object with attributes: outcome (str), normalized_data (dict), raw_event_id (str), tenant_id (UUID), flow_id (str)
        db: AsyncSession

    Returns:
        None

    Raises:
        ValueError: on invariant violations
    """
    outcome = getattr(event, "outcome", None)
    if outcome not in {"new_quote", "follow_up", "ignored", "unassigned"}:
        raise ValueError(f"Unknown outcome: {outcome}")

    tenant_id = getattr(event, "tenant_id", None)
    raw_event_id = getattr(event, "raw_event_id", None)
    flow_id = getattr(event, "flow_id", "preventivi_v1")

    if outcome in {"ignored", "unassigned"}:
        return

    # Idempotency check: if we already have a ReceivedEmail with this external_ref, consider processed
    if raw_event_id:
        res = await db.execute(select(ReceivedEmail).where(ReceivedEmail.external_ref == str(raw_event_id)))
        existing = res.scalar_one_or_none()
        if existing:
            # Already processed this raw event for DB side-effects; no-op
            return

    # Prepare received email record (to be inserted for both new_quote and follow_up)
    received_values = {
        "id": uuid4(),
        "tenant_id": tenant_id,
        "channel": "email",
        "identifier": None,
        "external_ref": str(raw_event_id) if raw_event_id else None,
        "outcome": outcome,
        "processed": False,
        "raw_payload": event.normalized_data if hasattr(event, "normalized_data") else None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    if outcome == "new_quote":
        # 1) Upsert Customer by email
        customer_info = event.normalized_data.get("customer", {}) if hasattr(event, "normalized_data") else {}
        cust_email = customer_info.get("email")
        cust_name = customer_info.get("name") or ""

        customer_id = None
        if cust_email:
            res = await db.execute(select(Customer).where(Customer.email == cust_email).where(Customer.tenant_id == tenant_id))
            existing_cust = res.scalar_one_or_none()
            if existing_cust:
                customer_id = existing_cust.id
            else:
                # create customer row
                new_cust_id = uuid4()
                await db.execute(
                    Customer.__table__.insert().values(
                        id=new_cust_id,
                        tenant_id=tenant_id,
                        flow_id=flow_id,
                        name=cust_name,
                        email=cust_email,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                )
                customer_id = new_cust_id

        # 2) Create Quote if not exists for this raw_event (idempotency)
        # We avoid duplicate quotes by checking ReceivedEmail existence above
        quote_id = uuid4()
        quote_values = {
            "id": quote_id,
            "tenant_id": tenant_id,
            "flow_id": flow_id,
            "customer_id": customer_id,
            "quote_data": event.normalized_data.get("quote", {}),
            "status": "New",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        # Data consegna = now + 30 days (store in quote_data as a convenience)
        quote_values["quote_data"] = quote_values["quote_data"].copy()
        quote_values["quote_data"]["data_consegna"] = (datetime.utcnow() + timedelta(days=30)).isoformat()

        await db.execute(Quote.__table__.insert().values(**quote_values))

        # 3) Insert ReceivedEmail log
        await db.execute(ReceivedEmail.__table__.insert().values(**received_values))

        return

    if outcome == "follow_up":
        # Only append ReceivedEmail log
        await db.execute(ReceivedEmail.__table__.insert().values(**received_values))
        return
