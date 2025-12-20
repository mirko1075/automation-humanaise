"""
app/core/normalizer/service.py

Normalizer V1 orchestration: parse -> classify -> dispatch -> mark RawEvent processed

This module performs no business logic; it only orchestrates existing components
and ensures transactional integrity and idempotency.
"""
# TODO(observability): add structured trace for per-event decisions (classification reason)
# TODO(replay): admin endpoint to re-run normalizer for RawEvent id (see admin APIs)
# TODO(alerting): alert if normalizer fails >3 times for same RawEvent
# TODO(v2): persist classification outcome on RawEvent for auditing
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, update

from app.db.session import SessionLocal
from app.db.models import RawEvent, NormalizedEvent as NormalizedEventModel
from app.core.classifier import classify
from app.integrations.gmail_api import fetch_message as fetch_gmail_message
from app.core.dispatcher import dispatch
from app.monitoring.logger import log as app_log
from app.core.normalizer import llm_service


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
    result_dto: Optional[NormalizedEventDTO] = None
    try:
        async with SessionLocal() as db:
            async with db.begin():
                # Load RawEvent
                res = await db.execute(select(RawEvent).where(RawEvent.id == raw_event_id))
                raw = res.scalar_one_or_none()
                # Some test DB backends (sqlite) may store UUIDs as text; if not
                # found by UUID object, try string comparison as a fallback.
                if raw is None:
                    # Fallback: some DB backends (sqlite) store UUIDs as text.
                    # Try casting the id column to string for comparison.
                    try:
                        from sqlalchemy import cast, String as _String

                        res2 = await db.execute(select(RawEvent).where(cast(RawEvent.id, _String) == str(raw_event_id)))
                        raw = res2.scalar_one_or_none()
                    except Exception:
                        # Last-ditch fallback: match id against string directly
                        res2 = await db.execute(select(RawEvent).where(RawEvent.id == str(raw_event_id)))
                        raw = res2.scalar_one_or_none()
                if raw is None:
                    return None
                if getattr(raw, "processed", False):
                    return None

                # parse_email expected to be part of ingestion pipeline; here assume payload contains parsed email
                payload = getattr(raw, "payload", {}) or {}
                # defensively get email_data from payload or expect a nested 'parsed' key
                email_data = payload.get("parsed") if isinstance(payload.get("parsed"), dict) else payload

                # If email_data doesn't contain parsed message fields, attempt
                # to fetch the full message via Gmail API (tests patch this
                # function to return a fake MIME dict). Prefer using the
                # lightweight LLM classifier if available (tests patch it),
                # otherwise fall back to deterministic classifier.classify.
                if not isinstance(email_data, dict) or not (email_data.get("subject") or email_data.get("text_plain") or email_data.get("from_email") or email_data.get("from_name")):
                    # Try to fetch full message using messageId if present in payload
                    msg_id = payload.get("messageId") or payload.get("message_id") or payload.get("messageId")
                    if msg_id:
                        try:
                            fetched = await fetch_gmail_message(msg_id)
                            if isinstance(fetched, dict):
                                email_data = fetched
                        except Exception:
                            # If fetch fails, continue with existing minimal payload
                            pass

                try:
                    classification = await llm_service.classify_event(email_data)
                    # llm_service.classify_event may return a simple label string
                    if isinstance(classification, str):
                        classification = {"outcome": classification, "reason": "llm"}
                except Exception:
                    classification = await classify(email_data, raw.tenant_id, db)

                outcome = classification.get("outcome")
                reason = classification.get("reason")

                # Build normalized event record and DTO
                # Extract entities (LLM or rule-based extractor) to enrich normalized payload
                try:
                    entities = await llm_service.extract_entities(email_data)
                except Exception:
                    entities = None

                normalized_values = {
                    "tenant_id": raw.tenant_id,
                    "flow_id": raw.flow_id or "preventivi_v1",
                    "event_type": "email.received",
                    "normalized_data": {
                            "source": "email",
                            "classification": classification,
                            "email": email_data,
                            "entities": entities,
                            "customer": {
                                "email": (entities.get("email") if isinstance(entities, dict) and entities.get("email") else email_data.get("from_email")),
                                "name": (entities.get("nome") or entities.get("name") if isinstance(entities, dict) else None) or email_data.get("from_name") or "",
                                "phone": (entities.get("telefono") or entities.get("phone") if isinstance(entities, dict) else None),
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
                # Instrumentation: log DTO details to help trace why Customers/Quotes
                # are not created in some E2E tests. This log is lightweight and
                # will include tenant/flow/outcome and the normalized_data keys.
                try:
                    normalized_keys = list(dto.normalized_data.keys()) if isinstance(dto.normalized_data, dict) else None
                except Exception:
                    normalized_keys = None
                app_log(
                    "INFO",
                    "Dispatching normalized event",
                    component="normalizer",
                    tenant_id=str(dto.tenant_id),
                    flow_id=dto.flow_id,
                    raw_event_id=str(dto.raw_event_id),
                    outcome=dto.outcome,
                    normalized_keys=normalized_keys,
                )

                await dispatch(dto, db)

                # Mark RawEvent processed
                await db.execute(
                    update(RawEvent)
                    .where(RawEvent.id == raw_event_id)
                    .values(processed=True, updated_at=datetime.utcnow())
                )

                # Do not invoke business flows inside the DB transaction to avoid
                # visibility/isolation issues for newly committed rows. Capture
                # the DTO here and route it after the transaction commits so
                # downstream flows run in their own DB sessions.
                result_dto = dto
            # end transaction
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

    # At this point the transaction committed successfully. Route the
    # normalized event to the business flow so it can perform higher-level
    # processing (PreventiviV1 will enqueue WhatsApp notifications). We run
    # routing in the same coroutine but outside the DB transaction so the
    # business flow uses its own DB sessions.
    try:
        from app.core.router import route_normalized_event
        if result_dto is not None:
            await route_normalized_event(result_dto.id)
    except Exception:
        # Routing failures should not crash the normalizer; log and continue.
        try:
            app_log("ERROR", "Failed to route normalized event", component="normalizer", raw_event_id=str(raw_event_id))
        except Exception:
            pass

    # Return the DTO for the caller (tests expect the normalized DTO on success)
    return result_dto
