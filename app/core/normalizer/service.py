"""Normalization service: read a RawEvent, classify and enrich it, persist a
NormalizedEvent, then dispatch and route it to business flows.

This module provides a single coroutine `normalize_raw_event(raw_event_id)`
which is used by the ingestion pipeline and tests.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID
import time

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
    """Small DTO returned by normalize_raw_event for downstream routing/tests."""

    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        flow_id: str,
        outcome: Optional[str],
        reason: Optional[str],
        normalized_data: dict,
        raw_event_id: UUID,
    ) -> None:
        self.id = id
        self.tenant_id = tenant_id
        self.flow_id = flow_id
        self.outcome = outcome
        self.reason = reason
        self.normalized_data = normalized_data
        self.raw_event_id = raw_event_id


async def normalize_raw_event(raw_event_id: UUID) -> Optional[NormalizedEventDTO]:
    """Normalize a RawEvent and return a DTO on success.

    The function runs a DB transaction to create the NormalizedEvent and mark
    the RawEvent as processed. It handles concurrent-insert IntegrityError by
    reading the existing normalized event.
    """
    start_ts = time.monotonic()
    result_dto: Optional[NormalizedEventDTO] = None

    app_log("INFO", "normalizer.start", component="normalizer", raw_event_id=str(raw_event_id))
    try:
        await audit_event_fn("normalizer.start", None, None, {"raw_event_id": str(raw_event_id)})
    except Exception:
        pass

    try:
        async with SessionLocal() as db:
            async with db.begin():
                # Try to load the RawEvent. Some DB backends store UUIDs as text
                # so attempt a cast fallback if direct lookup fails.
                res = await db.execute(select(RawEvent).where(RawEvent.id == raw_event_id))
                raw = res.scalar_one_or_none()
                if raw is None:
                    try:
                        from sqlalchemy import cast, String as _String

                        res2 = await db.execute(
                            select(RawEvent).where(cast(RawEvent.id, _String) == str(raw_event_id))
                        )
                        raw = res2.scalar_one_or_none()
                    except Exception:
                        res2 = await db.execute(select(RawEvent).where(RawEvent.id == str(raw_event_id)))
                        raw = res2.scalar_one_or_none()

                if raw is None:
                    return None
                if getattr(raw, "processed", False):
                    return None

                payload = getattr(raw, "payload", {}) or {}
                email_data = payload.get("parsed") if isinstance(payload.get("parsed"), dict) else payload

                # If payload is minimal, attempt to fetch full message by id
                if not isinstance(email_data, dict) or not (
                    email_data.get("subject") or email_data.get("text_plain") or email_data.get("from_email") or email_data.get("from_name")
                ):
                    msg_id = payload.get("messageId") or payload.get("message_id")
                    if msg_id:
                        try:
                            fetched = await fetch_gmail_message(msg_id)
                            if isinstance(fetched, dict):
                                email_data = fetched
                        except Exception:
                            pass

                # Prefer LLM-based classification when available, fall back to rule-based
                try:
                    classification = await llm_service.classify_event(email_data)
                    if isinstance(classification, str):
                        classification = {"outcome": classification, "reason": "llm"}
                except Exception:
                    classification = await classify(email_data, raw.tenant_id, db)

                outcome = classification.get("outcome") if isinstance(classification, dict) else None
                reason = classification.get("reason") if isinstance(classification, dict) else None

                try:
                    entities = await llm_service.extract_entities(email_data)
                except Exception:
                    entities = None

                normalized_payload = {
                    "tenant_id": raw.tenant_id,
                    "flow_id": raw.flow_id or "preventivi_v1",
                    "event_type": "email.received",
                    "normalized_data": {
                        "source": "email",
                        "classification": classification,
                        "email": email_data,
                        "entities": entities,
                        "customer": {
                            "email": (
                                entities.get("email") if isinstance(entities, dict) and entities.get("email") else email_data.get("from_email")
                            ),
                            "name": (
                                (entities.get("nome") or entities.get("name") if isinstance(entities, dict) else None)
                                or email_data.get("from_name")
                                or ""
                            ),
                            "phone": (
                                (entities.get("telefono") or entities.get("phone") if isinstance(entities, dict) else None)
                            ),
                        },
                        "quote": {},
                    },
                    "status": "processed",
                }

                norm = NormalizedEventModel(
                    tenant_id=normalized_payload["tenant_id"],
                    flow_id=normalized_payload["flow_id"],
                    event_type=normalized_payload["event_type"],
                    normalized_data=normalized_payload["normalized_data"],
                    status=normalized_payload["status"],
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

                # Mark RawEvent processed inside same transaction
                await db.execute(
                    update(RawEvent).where(RawEvent.id == raw_event_id).values(processed=True, updated_at=datetime.utcnow())
                )

                result_dto = dto

    except Exception as exc:
        # Handle concurrent insert race: return existing normalized event if present
        if isinstance(exc, IntegrityError):
            app_log(
                "WARNING",
                "IntegrityError inserting NormalizedEvent; possible duplicate due to concurrent normalizer runs",
                component="normalizer",
                raw_event_id=str(raw_event_id),
            )
            async with SessionLocal() as db2:
                res_dup = await db2.execute(select(NormalizedEventModel).where(NormalizedEventModel.raw_event_id == raw_event_id))
                existing_norm = res_dup.scalar_one_or_none()
                if existing_norm:
                    result_dto = NormalizedEventDTO(
                        id=existing_norm.id,
                        tenant_id=existing_norm.tenant_id,
                        flow_id=existing_norm.flow_id,
                        outcome=getattr(existing_norm, "outcome", "unknown"),
                        reason="duplicate_due_to_concurrency",
                        normalized_data=existing_norm.normalized_data,
                        raw_event_id=raw_event_id,
                    )
                else:
                    raise
        else:
            # Mark raw as not processed in a fresh session to allow retry
            async with SessionLocal() as db2:
                async with db2.begin():
                    await db2.execute(
                        update(RawEvent).where(RawEvent.id == raw_event_id).values(processed=False, updated_at=datetime.utcnow())
                    )

        try:
            duration_ms = int((time.monotonic() - start_ts) * 1000)
            try:
                await audit_event_fn(
                    "normalizer.error",
                    None,
                    None,
                    {"raw_event_id": str(raw_event_id), "error": str(exc), "duration_ms": duration_ms},
                )
            except Exception:
                pass
        except Exception:
            pass
        raise

    # Route normalized event outside transaction so business flows use fresh DB sessions
    try:
        from app.core.router import route_normalized_event

        if result_dto is not None:
            await route_normalized_event(result_dto.id)
    except Exception:
        try:
            app_log("ERROR", "Failed to route normalized event", component="normalizer", raw_event_id=str(raw_event_id))
        except Exception:
            pass

    try:
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        try:
            await audit_event_fn(
                "normalizer.done",
                None,
                None,
                {"raw_event_id": str(raw_event_id), "normalized_id": str(result_dto.id) if result_dto else None, "duration_ms": duration_ms},
            )
        except Exception:
            pass
        app_log("INFO", "normalizer.done", component="normalizer", raw_event_id=str(raw_event_id), duration_ms=duration_ms)
    except Exception:
        pass

    return result_dto
