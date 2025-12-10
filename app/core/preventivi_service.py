# app/core/preventivi_service.py
"""
Business logic for processing preventivi (construction quotes).
"""
from typing import Dict, Any, Optional
from uuid import UUID
from app.db.models import NormalizedEvent
from app.db.repositories.customer_repository import CustomerRepository
from app.db.repositories.quote_repository import QuoteRepository
from app.monitoring.logger import log
from app.monitoring.audit import audit_event
from app.monitoring.slack_alerts import send_slack_alert
from app.db.session import SessionLocal
from app.integrations.llm_service import classify_event, extract_entities
from app.integrations.whatsapp_api import WhatsAppMessenger
from app.integrations.onedrive_api import OneDriveConnector
import traceback

async def process_normalized_event(event: NormalizedEvent) -> None:
    """
    Process a normalized event and transform it into a structured quote.
    Args:
        event: NormalizedEvent instance
    """
    request_id = getattr(event, "request_id", None)
    tenant_id = event.tenant_id
    flow_id = event.flow_id
    event_id = event.id
    async with SessionLocal() as db:
        try:
            log("INFO", "PreventiviV1: classification started", module="preventivi_service", request_id=request_id, tenant_id=tenant_id, flow_id=flow_id, event_id=event_id)
            # 1. Classification
            classification = await classify_event(event)
            await audit_event("preventivi_classification", tenant_id, flow_id, {"event_id": str(event_id), "classification": classification}, request_id=request_id)
            if classification == "not_relevant":
                log("INFO", "PreventiviV1: event not relevant", module="preventivi_service", request_id=request_id, tenant_id=tenant_id, flow_id=flow_id, event_id=event_id)
                return
            # 2. Entity Extraction
            extracted = await extract_entities(event)
            await audit_event("preventivi_extraction", tenant_id, flow_id, {"event_id": str(event_id), "entities": extracted}, request_id=request_id)
            # 3. Customer Management
            customer_repo = CustomerRepository(db)
            customer = await find_or_create_customer(customer_repo, tenant_id, extracted)
            # 4. Quote Management
            quote_repo = QuoteRepository(db)
            if classification == "new_quote":
                quote = await quote_repo.create(
                    tenant_id=tenant_id,
                    flow_id=flow_id,
                    customer_id=customer.id,
                    quote_data=extracted,
                    status="OPEN",
                    pdf_url=None
                )
                await audit_event("quote_created", tenant_id, flow_id, {"quote_id": str(quote.id)}, request_id=request_id)
            elif classification == "existing_quote":
                quote = await find_and_update_quote(quote_repo, tenant_id, customer, event, extracted)
                await audit_event("quote_updated", tenant_id, flow_id, {"quote_id": str(quote.id)}, request_id=request_id)
            # 5. Prepare WhatsApp Notification
            messenger = WhatsAppMessenger()
            await messenger.enqueue_notification(
                tenant_id=tenant_id,
                phone=customer.phone,
                message_type="received",
                placeholders={"name": customer.name, "job": extracted.get("descrizione_lavori")}
            )
            await audit_event("wa_notification_enqueued", tenant_id, flow_id, {"customer_id": str(customer.id)}, request_id=request_id)
            # 6. Prepare OneDrive Excel Update
            onedrive = OneDriveConnector()
            await onedrive.enqueue_excel_update(quote)
            await audit_event("excel_update_enqueued", tenant_id, flow_id, {"quote_id": str(quote.id)}, request_id=request_id)
            log("INFO", "PreventiviV1: processing completed", module="preventivi_service", request_id=request_id, tenant_id=tenant_id, flow_id=flow_id, event_id=event_id)
        except Exception as exc:
            tb = traceback.format_exc()
            log("ERROR", f"PreventiviV1 error: {exc}", module="preventivi_service", request_id=request_id, tenant_id=tenant_id, flow_id=flow_id, event_id=event_id)
            await audit_event("preventivi_error", tenant_id, flow_id, {"event_id": str(event_id), "error": str(exc), "traceback": tb}, request_id=request_id)
            await send_slack_alert(
                message=f"PreventiviV1 error: {exc}",
                context={"event_id": str(event_id), "tenant_id": tenant_id, "flow_id": flow_id, "traceback": tb},
                severity="CRITICAL",
                module="preventivi_service",
                request_id=request_id
            )

async def find_or_create_customer(repo: CustomerRepository, tenant_id: str, extracted: Dict[str, Any]) -> Any:
    """
    Find or create a customer based on extracted entities.
    """
    phone = extracted.get("telefono")
    email = extracted.get("email")
    name = extracted.get("nome")
    customer = None
    if phone:
        customers = await repo.list_by_tenant(tenant_id)
        customer = next((c for c in customers if c.phone == phone), None)
    if not customer and email:
        customers = await repo.list_by_tenant(tenant_id)
        customer = next((c for c in customers if c.email == email), None)
    if not customer and name:
        customers = await repo.list_by_tenant(tenant_id)
        customer = next((c for c in customers if c.name == name), None)
    if customer:
        await audit_event("customer_updated", tenant_id, None, {"customer_id": str(customer.id)})
        return customer
    customer = await repo.create(
        tenant_id=tenant_id,
        flow_id=None,
        name=name or "Unknown",
        email=email,
        phone=phone
    )
    await audit_event("customer_created", tenant_id, None, {"customer_id": str(customer.id)})
    return customer

async def find_and_update_quote(repo: QuoteRepository, tenant_id: str, customer: Any, event: NormalizedEvent, extracted: Dict[str, Any]) -> Any:
    """
    Find and update an existing quote.
    """
    quotes = await repo.list_by_tenant(tenant_id)
    match = next((q for q in quotes if q.customer_id == customer.id and q.quote_data.get("subject") == event.normalized_data.get("subject")), None)
    if not match:
        match = await repo.create(
            tenant_id=tenant_id,
            flow_id=event.flow_id,
            customer_id=customer.id,
            quote_data=extracted,
            status="OPEN",
            pdf_url=None
        )
        await audit_event("quote_created", tenant_id, event.flow_id, {"quote_id": str(match.id)})
        return match
    # Update quote
    match.quote_data.update(extracted)
    await repo.update(match.id, quote_data=match.quote_data)
    await audit_event("quote_updated", tenant_id, event.flow_id, {"quote_id": str(match.id)})
    return match
