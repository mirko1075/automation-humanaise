# app/integrations/whatsapp_api.py
"""
WhatsApp API connector for Edilcos Automation Backend.
Handles sending WhatsApp messages via Facebook Graph API.
"""
from app.db.models import Notification, Tenant
from app.monitoring.logger import log
from app.monitoring.audit import audit_event
from app.monitoring.slack_alerts import send_slack_alert
from typing import Dict, Any
import aiohttp
import traceback

async def send_whatsapp_message(notification: Notification, tenant: Tenant) -> Dict[str, Any]:
    request_id = None
    try:
        url = f"https://graph.facebook.com/v19.0/{tenant.whatsapp_phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {tenant.whatsapp_access_token}",
            "Content-Type": "application/json"
        }
        payload = build_payload(notification)
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                resp_data = await resp.json()
                success = resp.status == 200 and "messages" in resp_data
                message_id = resp_data.get("messages", [{}])[0].get("id") if success else None
                await audit_event(
                    "whatsapp_sent" if success else "whatsapp_failed",
                    notification.tenant_id,
                    None,
                    {"notification_id": str(notification.id), "response": resp_data},
                    request_id=request_id
                )
                log("INFO" if success else "ERROR", f"WhatsApp send result: {resp_data}", module="whatsapp_api", tenant_id=notification.tenant_id)
                return {
                    "success": success,
                    "message_id": message_id,
                    "raw_response": resp_data
                }
    except Exception as exc:
        tb = traceback.format_exc()
        log("ERROR", f"WhatsApp send error: {exc}", module="whatsapp_api", tenant_id=notification.tenant_id)
        await audit_event("whatsapp_send_error", notification.tenant_id, None, {"notification_id": str(notification.id), "error": str(exc), "traceback": tb}, request_id=request_id)
        await send_slack_alert(
            message=f"WhatsApp send error: {exc}",
            context={"notification_id": str(notification.id), "tenant_id": notification.tenant_id, "traceback": tb},
            severity="CRITICAL",
            module="whatsapp_api",
            request_id=request_id
        )
        return {"success": False}

def build_payload(notification: Notification) -> Dict[str, Any]:
    p = notification.payload
    if p["type"] == "text":
        return {
            "messaging_product": "whatsapp",
            "to": p["phone"],
            "type": "text",
            "text": {"preview_url": False, "body": p["message"]}
        }
    elif p["type"] == "template":
        return {
            "messaging_product": "whatsapp",
            "to": p["phone"],
            "type": "template",
            "template": {
                "name": p["template_name"],
                "language": {"code": "it"},
                "components": [
                    {"type": "body", "parameters": p.get("placeholders", [])}
                ]
            }
        }
    elif p["type"] == "media":
        return {
            "messaging_product": "whatsapp",
            "to": p["phone"],
            "type": "document",
            "document": {
                "link": p["media_url"],
                "caption": p.get("caption", "")
            }
        }
    return {}
