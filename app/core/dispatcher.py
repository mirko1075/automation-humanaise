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
# TODO(v2): use DB-level UPSERT (ON CONFLICT) to minimize race windows in dispatcher
# TODO(perf): batch dispatcher writes in high-throughput tenants
# TODO(ops): instrument per-tenant dispatcher failure rate metrics
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from typing import Any

from sqlalchemy import select
from app.db.models import Customer, Quote, ReceivedEmail
from app.monitoring.logger import log as app_log


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
    # Determine flow_id and log incoming event summary to help trace E2E failures
    flow_id = getattr(event, "flow_id", "preventivi_v1")
    try:
        nd = event.normalized_data if hasattr(event, "normalized_data") else None
        nd_keys = list(nd.keys()) if isinstance(nd, dict) else None
    except Exception:
        nd_keys = None
    app_log("INFO", "dispatcher invoked", component="dispatcher", tenant_id=str(tenant_id) if tenant_id else None, flow_id=flow_id, raw_event_id=str(raw_event_id) if raw_event_id else None, outcome=outcome, normalized_keys=nd_keys)

    if outcome in {"ignored", "unassigned"}:
        return

    # Idempotency check: if we already have a ReceivedEmail with this external_ref, consider processed
    if raw_event_id:
        res = await db.execute(select(ReceivedEmail).where(ReceivedEmail.external_ref == str(raw_event_id)))
        existing = res.scalar_one_or_none()
        if existing:
            # Already processed this raw event for DB side-effects; no-op
            app_log("INFO", "dispatch no-op: already processed (ReceivedEmail exists)", component="dispatcher", tenant_id=str(tenant_id) if tenant_id else None, raw_event_id=str(raw_event_id))
            return
        else:
            app_log("DEBUG", "no existing ReceivedEmail found; proceeding", component="dispatcher", tenant_id=str(tenant_id) if tenant_id else None, raw_event_id=str(raw_event_id))

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
        app_log("INFO", "new_quote payload summary", component="dispatcher", tenant_id=str(tenant_id) if tenant_id else None, flow_id=flow_id, raw_event_id=str(raw_event_id) if raw_event_id else None, customer_info=customer_info, normalized_data=event.normalized_data)
        # Fallback: some normalized events place extracted entities at top-level
        if not customer_info:
            nd = event.normalized_data if hasattr(event, "normalized_data") else {}
            # prefer 'entities' key, then top-level entity keys used by LLM
            candidate = nd.get("entities") if isinstance(nd.get("entities"), dict) else nd
            # map common keys to email/name/phone
            mapped = {
                "email": candidate.get("email") if isinstance(candidate.get("email"), str) else candidate.get("from_email") if isinstance(candidate.get("from_email"), str) else None,
                "name": candidate.get("nome") or candidate.get("name") or (f"{candidate.get('nome','')} {candidate.get('cognome','')}".strip() if candidate.get('nome') else None),
                "phone": candidate.get("telefono") or candidate.get("phone") or candidate.get("telefono_principale")
            }
            customer_info = {k: v for k, v in mapped.items() if v is not None}

        cust_email = customer_info.get("email")
        cust_name = customer_info.get("name") or ""
        cust_phone = customer_info.get("phone") or customer_info.get("telefono")

        customer_id = None
        app_log("INFO", "candidate customer fields", component="dispatcher", tenant_id=str(tenant_id) if tenant_id else None, flow_id=flow_id, email=cust_email, name=cust_name, phone=cust_phone)
        # Prefer email-based lookup/upsert, fallback to phone-based upsert
        if cust_email:
            res = await db.execute(select(Customer).where(Customer.email == cust_email).where(Customer.tenant_id == tenant_id))
            existing_cust = res.scalar_one_or_none()
            if existing_cust:
                customer_id = existing_cust.id
            else:
                # create customer row (use ORM insert + flush for visibility)
                new_cust_id = uuid4()
                await db.execute(
                    Customer.__table__.insert().values(
                        id=new_cust_id,
                        tenant_id=tenant_id,
                        flow_id=flow_id,
                        name=cust_name,
                        email=cust_email,
                        phone=cust_phone,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                )
                customer_id = new_cust_id
                try:
                    await db.flush()
                    app_log("INFO", "Customer created by email", component="dispatcher", tenant_id=str(tenant_id), flow_id=flow_id, customer_id=str(customer_id), email=cust_email)
                except Exception:
                    app_log("ERROR", "failed_flush_after_customer_insert", component="dispatcher", tenant_id=str(tenant_id), flow_id=flow_id)
                # Diagnostic: count customers for tenant to ensure visibility in same transaction
                try:
                    res_count = await db.execute(select(Customer).where(Customer.tenant_id == tenant_id))
                    customers_now = res_count.scalars().all()
                    app_log("DEBUG", "post_insert_customer_count", component="dispatcher", tenant_id=str(tenant_id), count=len(customers_now))
                except Exception:
                    app_log("DEBUG", "post_insert_customer_count_failed", component="dispatcher", tenant_id=str(tenant_id))
        elif cust_phone:
            # Try to find existing customer by phone
            res = await db.execute(select(Customer).where(Customer.phone == cust_phone).where(Customer.tenant_id == tenant_id))
            existing_cust = res.scalar_one_or_none()
            if existing_cust:
                customer_id = existing_cust.id
            else:
                new_cust_id = uuid4()
                await db.execute(
                    Customer.__table__.insert().values(
                        id=new_cust_id,
                        tenant_id=tenant_id,
                        flow_id=flow_id,
                        name=cust_name,
                        email=None,
                        phone=cust_phone,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                )
                customer_id = new_cust_id
                try:
                    await db.flush()
                    app_log("INFO", "Customer created by phone", component="dispatcher", tenant_id=str(tenant_id), flow_id=flow_id, customer_id=str(customer_id), phone=cust_phone)
                except Exception:
                    app_log("ERROR", "failed_flush_after_customer_insert", component="dispatcher", tenant_id=str(tenant_id), flow_id=flow_id)
        else:
            app_log("WARNING", "Could not determine customer identity (no email/phone)", component="dispatcher", tenant_id=str(tenant_id) if tenant_id else None, flow_id=flow_id, raw_event_id=str(raw_event_id) if raw_event_id else None)

        # 2) Create Quote if not exists for this raw_event (idempotency)
        # We avoid duplicate quotes by checking ReceivedEmail existence above
        quote_id = uuid4()
        # Build quote_data from normalized payload or extracted entities
        quote_payload = (event.normalized_data.get("quote") if isinstance(event.normalized_data, dict) else None) or {}
        entities = (event.normalized_data.get("entities") if isinstance(event.normalized_data, dict) else None) or {}
        # prefer explicit quote fields, fallback to entities extracted by LLM
        descrizione = quote_payload.get("descrizione_lavori") or entities.get("descrizione_lavori") or entities.get("descrizione")
        quote_values = {
            "id": quote_id,
            "tenant_id": tenant_id,
            "flow_id": flow_id,
            "customer_id": customer_id,
            "quote_data": quote_payload.copy(),
            "status": "OPEN",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        # Ensure description and delivery date are present
        if descrizione:
            quote_values["quote_data"]["descrizione_lavori"] = descrizione
        quote_values["quote_data"]["data_consegna"] = (datetime.utcnow() + timedelta(days=30)).isoformat()

        await db.execute(Quote.__table__.insert().values(**quote_values))
        try:
            await db.flush()
            app_log("INFO", "Quote inserted", component="dispatcher", tenant_id=str(tenant_id), flow_id=flow_id, quote_id=str(quote_id), customer_id=str(customer_id))
        except Exception:
            app_log("ERROR", "failed_flush_after_quote_insert", component="dispatcher", tenant_id=str(tenant_id), flow_id=flow_id)
        # Diagnostic: count quotes for tenant to ensure visibility in same transaction
        try:
            qcount = await db.execute(select(Quote).where(Quote.tenant_id == tenant_id))
            quotes_now = qcount.scalars().all()
            app_log("DEBUG", "post_insert_quote_count", component="dispatcher", tenant_id=str(tenant_id), count=len(quotes_now))
        except Exception:
            app_log("DEBUG", "post_insert_quote_count_failed", component="dispatcher", tenant_id=str(tenant_id))

        # 3) Insert ReceivedEmail log
        # set identifier to email or phone if available
        if customer_info:
            if received_values.get("identifier") is None:
                received_values["identifier"] = customer_info.get("email") or customer_info.get("phone")
        await db.execute(ReceivedEmail.__table__.insert().values(**received_values))
        app_log("INFO", "ReceivedEmail inserted", component="dispatcher", tenant_id=str(tenant_id), flow_id=flow_id, external_ref=received_values.get("external_ref"))

        return

    if outcome == "follow_up":
        # Only append ReceivedEmail log
        await db.execute(ReceivedEmail.__table__.insert().values(**received_values))
        return
