# app/api/notifications/whatsapp.py
"""
High-level WhatsAppMessenger API for Edilcos Automation Backend.
"""
from app.db.session import SessionLocal
from app.db.repositories.notification_repository import NotificationRepository
from app.db.repositories.tenant_repository import TenantRepository
from app.db.models import Notification
from app.monitoring.logger import log
from app.monitoring.audit import audit_event
from uuid import UUID
from typing import Optional, Dict, Any
import traceback

async def enqueue_text_message(tenant_id: UUID, phone: str, message: str, context: Optional[Dict[str, Any]] = None) -> Notification:
    async with SessionLocal() as db:
        repo = NotificationRepository(db)
        notification = await repo.create(
            tenant_id=tenant_id,
            flow_id=None,
            event_id=None,
            channel="whatsapp",
            message=message,
            status="pending",
            payload={"type": "text", "phone": phone, "message": message, "context": context}
        )
        await audit_event("whatsapp_enqueued", tenant_id, None, {"notification_id": str(notification.id), "type": "text"})
        log("INFO", f"WhatsApp text message enqueued for {phone}", module="whatsapp_api", tenant_id=tenant_id)
        return notification

async def enqueue_template_message(tenant_id: UUID, phone: str, template_name: str, placeholders: Optional[Dict[str, Any]] = None) -> Notification:
    async with SessionLocal() as db:
        repo = NotificationRepository(db)
        notification = await repo.create(
            tenant_id=tenant_id,
            flow_id=None,
            event_id=None,
            channel="whatsapp",
            message=template_name,
            status="pending",
            payload={"type": "template", "phone": phone, "template_name": template_name, "placeholders": placeholders}
        )
        await audit_event("whatsapp_enqueued", tenant_id, None, {"notification_id": str(notification.id), "type": "template"})
        log("INFO", f"WhatsApp template message enqueued for {phone}", module="whatsapp_api", tenant_id=tenant_id)
        return notification

async def enqueue_media_message(tenant_id: UUID, phone: str, media_url: str, caption: Optional[str] = None) -> Notification:
    async with SessionLocal() as db:
        repo = NotificationRepository(db)
        notification = await repo.create(
            tenant_id=tenant_id,
            flow_id=None,
            event_id=None,
            channel="whatsapp",
            message=caption or "",
            status="pending",
            payload={"type": "media", "phone": phone, "media_url": media_url, "caption": caption}
        )
        await audit_event("whatsapp_enqueued", tenant_id, None, {"notification_id": str(notification.id), "type": "media"})
        log("INFO", f"WhatsApp media message enqueued for {phone}", module="whatsapp_api", tenant_id=tenant_id)
        return notification
