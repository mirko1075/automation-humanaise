# app/core/router.py
"""
FlowRouter for Edilcos Automation Backend.
Routes normalized events to the appropriate business flow module.
"""
from uuid import UUID
from typing import Callable, Dict, Any, Awaitable
from app.monitoring.logger import log
from app.monitoring.audit import audit_event
from app.monitoring.slack_alerts import send_slack_alert
from app.db.session import SessionLocal
from app.db.repositories.normalized_event_repository import NormalizedEventRepository
from app.db.repositories.tenant_repository import TenantRepository
from app.core.preventivi_service import process_normalized_event as preventivi_handler
import traceback

# Registry for flow handlers (easy to extend)
FLOW_HANDLERS: Dict[str, Callable[[Any], Awaitable[Any]]] = {
    "preventivi_v1": preventivi_handler,
    # "documenti_v1": documenti_service.process_normalized_event,
    # "attrezzature_v1": attrezzature_service.process_normalized_event,
    # "urgenze_v1": urgenze_service.process_normalized_event,
}

async def route_normalized_event(normalized_event_id: UUID) -> None:
    """
    Route a normalized event to the correct business flow handler.
    Args:
        normalized_event_id: UUID of the NormalizedEvent
    """
    async with SessionLocal() as db:
        repo = NormalizedEventRepository(db)
        event = await repo.get(normalized_event_id)
        if not event:
            log("ERROR", f"NormalizedEvent not found: {normalized_event_id}", module="router", request_id=None)
            await audit_event("flow_routing_failed", None, None, {"normalized_event_id": str(normalized_event_id), "error": "not_found"})
            return
        tenant_id = event.tenant_id
        flow_id = event.flow_id
        source = getattr(event, "source", None) or event.normalized_data.get("source")
        log("INFO", f"Flow routing started for event {normalized_event_id}", module="router", request_id=None, tenant_id=tenant_id, flow_id=flow_id)
        await audit_event("flow_routing_started", tenant_id, flow_id, {"normalized_event_id": str(normalized_event_id)})
        try:
            # MVP: Only PreventiviV1 for email/preventivi_v1
            if source == "email" and flow_id == "preventivi_v1":
                handler = FLOW_HANDLERS.get(flow_id)
                if handler:
                    await handler(event)
                    log("INFO", f"Flow routing completed for event {normalized_event_id}", module="router", request_id=None, tenant_id=tenant_id, flow_id=flow_id)
                    await audit_event("flow_routing_completed", tenant_id, flow_id, {"normalized_event_id": str(normalized_event_id)})
                    return
            # Extension point for other flows
            log("WARNING", f"Unsupported flow: source={source}, flow_id={flow_id}", module="router", request_id=None, tenant_id=tenant_id, flow_id=flow_id)
            await audit_event("unsupported_flow", tenant_id, flow_id, {"normalized_event_id": str(normalized_event_id), "source": source, "flow_id": flow_id})
        except Exception as exc:
            tb = traceback.format_exc()
            log("ERROR", f"Flow routing failed: {exc}", module="router", request_id=None, tenant_id=tenant_id, flow_id=flow_id)
            await audit_event("flow_routing_failed", tenant_id, flow_id, {"normalized_event_id": str(normalized_event_id), "error": str(exc), "traceback": tb})
            await send_slack_alert(
                message=f"Flow routing error: {exc}",
                context={"normalized_event_id": str(normalized_event_id), "tenant_id": tenant_id, "flow_id": flow_id, "traceback": tb},
                severity="CRITICAL",
                module="router",
                request_id=None
            )
