# app/core/normalizer.py
"""
Event normalizer: converts RawEvent into a NormalizedEvent and dispatches to FlowRouter.
"""
# app/core/normalizer.py
"""
Event normalizer: converts RawEvent into a NormalizedEvent and dispatches to FlowRouter.
"""
from typing import Any, Dict
# app/core/normalizer.py
"""
Event normalizer: converts RawEvent into a NormalizedEvent and dispatches to FlowRouter.
"""
from typing import Any, Dict
from uuid import UUID
import traceback

from app.db.session import SessionLocal
from app.db.repositories.raw_event_repository import RawEventRepository
from app.db.repositories.normalized_event_repository import NormalizedEventRepository
from app.monitoring.logger import log
from app.monitoring.audit import audit_event
from app.monitoring.errors import record_error
from app.integrations import llm_service
from app.core.router import route_normalized_event


async def normalize_raw_event(raw_event_id: UUID) -> None:
    """
    Normalize a RawEvent into a NormalizedEvent and dispatch it to the FlowRouter.

    Args:
        raw_event_id: UUID of the RawEvent to normalize
    """
    async with SessionLocal() as db:
        raw_repo = RawEventRepository(db)
        normalized_repo = NormalizedEventRepository(db)
        try:
            raw = await raw_repo.get(raw_event_id)
            if not raw:
                log("ERROR", f"RawEvent not found: {raw_event_id}", module="normalizer")
                await audit_event("normalizer_failed", None, None, {"raw_event_id": str(raw_event_id), "error": "not_found"})
                return

            tenant_id = raw.tenant_id
            log("INFO", f"Normalizing RawEvent {raw_event_id}", module="normalizer", tenant_id=tenant_id)
            await audit_event("normalizer_started", tenant_id, None, {"raw_event_id": str(raw_event_id)})

            # 1. Classify & extract (synchronous calls)
            classification = llm_service.classify_event(raw)
            entities = llm_service.extract_entities(raw)

            # Safely read payload (raw.payload may be a dict, JSON string, or other)
            payload = {}
            try:
                p = getattr(raw, "payload", None)
                if isinstance(p, dict):
                    payload = p
                elif isinstance(p, str):
                    import json as _json
                    try:
                        payload = _json.loads(p)
                    except Exception:
                        payload = {}
                else:
                    # attempt to convert via mapping protocol
                    if hasattr(p, "items"):
                        payload = dict(p)
                    else:
                        payload = {}
            except Exception:
                payload = {}

            log("DEBUG", f"Classification={classification}", module="normalizer", tenant_id=tenant_id)
            log("DEBUG", f"Entities={entities}", module="normalizer", tenant_id=tenant_id)

            # Normalize source for routing: map 'gmail' -> 'email'
            normalized_source = "email" if (getattr(raw, "source", None) == "gmail") else getattr(raw, "source", None)

            normalized_data: Dict[str, Any] = {
                "source": normalized_source,
                "subject": getattr(raw, "subject", None) or payload.get("subject"),
                "body": getattr(raw, "raw_text", None) or payload.get("body"),
                "sender": {"email": getattr(raw, "sender", None)},
                "attachments": getattr(raw, "attachments", []) or [],
                "entities": entities,
            }

            flow_id = "preventivi_v1" if classification in ("new_quote", "existing_quote") else (payload.get("flow_id") or "preventivi_v1")

            normalized = await normalized_repo.create(
                tenant_id=tenant_id,
                flow_id=flow_id,
                event_type=classification or "unknown",
                normalized_data=normalized_data,
                status="NEW",
            )

            raw.processed = True
            db.add(raw)
            await db.commit()

            await audit_event("normalizer_completed", tenant_id, flow_id, {"raw_event_id": str(raw_event_id), "normalized_id": str(normalized.id)})
            log("INFO", f"NormalizedEvent created {normalized.id}", module="normalizer", tenant_id=tenant_id, flow_id=flow_id)

            try:
                await route_normalized_event(normalized.id)
            except Exception as exc:
                tb = traceback.format_exc()
                await record_error(component="normalizer", function="route_normalized_event", message=str(exc), details={"normalized_id": str(normalized.id)}, stacktrace=tb)

        except Exception as exc:
            tb = traceback.format_exc()
            await record_error(component="normalizer", function="normalize_raw_event", message=str(exc), details={"raw_event_id": str(raw_event_id)}, stacktrace=tb)
            await audit_event("normalizer_exception", None, None, {"raw_event_id": str(raw_event_id), "error": str(exc), "traceback": tb})
            raw.processed = True
