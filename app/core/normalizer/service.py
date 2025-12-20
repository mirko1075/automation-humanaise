"""
app/core/normalizer/service.py

Normalizer V1 orchestration: parse -> classify -> dispatch -> mark RawEvent processed

This module performs no business logic; it only orchestrates existing components
and ensures transactional integrity and idempotency.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, update

from app.db.session import SessionLocal
from app.db.models import RawEvent, NormalizedEvent as NormalizedEventModel
from app.core.classifier import classify
from app.core.dispatcher import dispatch


class NormalizedEventDTO:
    def __init__(self, *, id: UUID, tenant_id: UUID, flow_id: str, outcome: str, reason: str, normalized_data: dict, raw_event_id: UUID):
        self.id = id
        self.tenant_id = tenant_id
        self.flow_id = flow_id
        self.outcome = outcome
        self.reason = reason
        self.normalized_data = normalized_data
        self.raw_event_id = raw_event_id


async def normalize_raw_event(raw_event_id: UUID) -> Optional[NormalizedEventDTO]:
    """Normalize a RawEvent by id.

    Steps:
      - open one async session
      - load RawEvent; exit if missing or already processed
      - parse payload using existing `parse_email` helper (assumed present in payload)
      - classify(email_data, tenant_id, db)
      - build normalized DTO
      - call dispatch(dto, db) (does not commit)
      - mark RawEvent processed and insert a NormalizedEvent row
      - commit transaction

    Returns NormalizedEventDTO on success, None if raw event not found or already processed.
    """
    try:
        async with SessionLocal() as db:
            async with db.begin():
                # Load RawEvent
                res = await db.execute(select(RawEvent).where(RawEvent.id == raw_event_id))
                raw = res.scalar_one_or_none()
                if raw is None:
                    return None
                if getattr(raw, "processed", False):
                    return None

                # parse_email expected to be part of ingestion pipeline; here assume payload contains parsed email
                payload = getattr(raw, "payload", {}) or {}
                # defensively get email_data from payload or expect a nested 'parsed' key
                email_data = payload.get("parsed") if isinstance(payload.get("parsed"), dict) else payload

                classification = await classify(email_data, raw.tenant_id, db)

                outcome = classification.get("outcome")
                reason = classification.get("reason")

                # Build normalized event record and DTO
                normalized_values = {
                    "tenant_id": raw.tenant_id,
                    "flow_id": raw.flow_id or "preventivi_v1",
                    "event_type": "email.received",
                    "normalized_data": {
                            "classification": classification,
                            "email": email_data,
                            "customer": {
                                "email": email_data.get("from_email"),
                                "name": email_data.get("from_name") or "",
                            },
                            "quote": {},
                        },
                    "status": "processed",
                }

                # Create a NormalizedEvent ORM object and flush to obtain PK
                norm = NormalizedEventModel(
                    tenant_id=normalized_values["tenant_id"],
                    flow_id=normalized_values["flow_id"],
                    event_type=normalized_values["event_type"],
                    normalized_data=normalized_values["normalized_data"],
                    status=normalized_values["status"],
                )
                db.add(norm)
                await db.flush()

                dto = NormalizedEventDTO(
                    id=norm.id,
                    tenant_id=norm.tenant_id,
                    flow_id=norm.flow_id,
                    outcome=outcome,
                    reason=reason,
                    normalized_data=norm.normalized_data,
                    raw_event_id=raw.id,
                )

                # Dispatch side-effects (idempotency handled inside dispatcher)
                await dispatch(dto, db)

                # Mark RawEvent processed
                await db.execute(
                    update(RawEvent)
                    .where(RawEvent.id == raw_event_id)
                    .values(processed=True, updated_at=datetime.utcnow())
                )

                return dto
    except Exception:
        # Transaction may be aborted; mark RawEvent as not-processed in a fresh session
        async with SessionLocal() as db2:
            async with db2.begin():
                await db2.execute(
                    update(RawEvent)
                    .where(RawEvent.id == raw_event_id)
                    .values(processed=False, updated_at=datetime.utcnow())
                )
        raise
