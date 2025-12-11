# app/api/ingress/gmail_webhook.py
"""
Gmail Pub/Sub webhook endpoint for Edilcos Automation Backend.
"""
from fastapi import APIRouter, Request, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from app.monitoring.logger import log
from app.monitoring.audit import audit_event
from app.monitoring.slack_alerts import send_slack_alert
from app.db.repositories.raw_event_repository import RawEventRepository
from app.db.repositories.tenant_repository import TenantRepository
from app.db.repositories.external_token_repository import ExternalTokenRepository
from app.db.session import SessionLocal
from app.integrations import gmail_api
from app.core.normalizer import normalize_raw_event
from uuid import UUID
import base64
import json
import traceback

router = APIRouter(prefix="/gmail", tags=["gmail"])

async def get_tenant_id(email_address: str, db):
    # Try ExternalToken first, then Tenant
    ext_token_repo = ExternalTokenRepository(db)
    tenant_repo = TenantRepository(db)
    ext_tokens = await ext_token_repo.list_by_external_id(email_address)
    if ext_tokens:
        return ext_tokens[0].tenant_id
    tenant = await tenant_repo.get(email_address)
    if tenant:
        return tenant.id
    return None

@router.post("/webhook")
async def gmail_webhook(request: Request, background_tasks: BackgroundTasks):
    request_id = getattr(request.state, "request_id", None)
    try:
        body = await request.json()
        envelope = body.get("message", {})
        data_b64 = envelope.get("data")
        if not data_b64:
            log("WARNING", "Missing data in Pub/Sub envelope", module="gmail_webhook", request_id=request_id)
            return JSONResponse(status_code=400, content={"error": "Missing data", "request_id": request_id})
        decoded = base64.urlsafe_b64decode(data_b64 + "==")
        payload = json.loads(decoded)
        history_id = payload.get("historyId")
        email_address = payload.get("emailAddress")
        message_id = payload.get("messageId")
        missing_fields = [f for f in ["historyId", "emailAddress", "messageId"] if not payload.get(f)]
        if missing_fields:
            log("WARNING", f"Missing fields: {missing_fields}", module="gmail_webhook", request_id=request_id)
        async with SessionLocal() as db:
            tenant_id = await get_tenant_id(email_address, db)
            if not tenant_id:
                log("ERROR", f"Tenant not found for {email_address}", module="gmail_webhook", request_id=request_id)
                await audit_event("gmail_ingress_failed", None, None, payload, request_id=request_id)
                return JSONResponse(status_code=404, content={"error": "Tenant not found", "request_id": request_id})
            raw_event_repo = RawEventRepository(db)
            # Idempotency check
            existing = await raw_event_repo.list_by_tenant(tenant_id)
            if any(e.idempotency_key == message_id for e in existing):
                log("INFO", f"Duplicate message_id {message_id}", module="gmail_webhook", request_id=request_id)
                return JSONResponse(content={"status": "received", "request_id": request_id})
            # Fetch Gmail message
            # TODO: Get access_token for Gmail API (from ExternalToken or config)
            access_token = "..."  # Replace with real token retrieval
            gmail_data = await gmail_api.fetch_message(message_id, access_token)
            raw_event = await raw_event_repo.create(
                tenant_id=tenant_id,
                flow_id=None,
                source="gmail",
                payload=payload,
                idempotency_key=message_id
            )
            # Save additional fields
            raw_event.subject = gmail_data["subject"]
            raw_event.sender = gmail_data["sender"]
            raw_event.raw_text = gmail_data["text_plain"]
            raw_event.raw_html = gmail_data["text_html"]
            raw_event.attachments = gmail_data["attachments"]
            await db.commit()
            await db.refresh(raw_event)
            await audit_event("gmail_ingress", tenant_id, None, payload, request_id=request_id)
            log("INFO", f"RawEvent saved for message_id {message_id}", module="gmail_webhook", request_id=request_id, tenant_id=tenant_id)
            # Pipeline handoff: schedule normalizer in background
            log("INFO", f"Handing off to EventNormalizer for raw_event_id {raw_event.id}", module="gmail_webhook", request_id=request_id, tenant_id=tenant_id)
            # Run normalizer inline (tests use in-process execution).
            await normalize_raw_event(raw_event.id)
            await audit_event("gmail_ingress_handoff", tenant_id, None, {"raw_event_id": str(raw_event.id)}, request_id=request_id)
        return JSONResponse(content={"status": "received", "request_id": request_id})
    except Exception as exc:
        tb = traceback.format_exc()
        log("ERROR", f"Exception in Gmail webhook: {exc}", module="gmail_webhook", request_id=request_id)
        await audit_event("gmail_ingress_exception", None, None, {"error": str(exc), "traceback": tb}, request_id=request_id)
        await send_slack_alert(f"Gmail webhook error: {exc}", context={"traceback": tb}, severity="CRITICAL", module="gmail_webhook", request_id=request_id)
        return JSONResponse(status_code=500, content={"error": "Internal Server Error", "request_id": request_id})
