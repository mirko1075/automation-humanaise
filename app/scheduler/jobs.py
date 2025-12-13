# app/scheduler/jobs.py
"""
Background jobs for Edilcos Automation Backend.
Handles notification retries, Excel updates, quote reminders, and health reports.
"""
from app.db.session import SessionLocal
from app.db.repositories.notification_repository import NotificationRepository
from app.db.repositories.tenant_repository import TenantRepository
from app.db.repositories.quote_repository import QuoteRepository
from app.db.repositories.customer_repository import CustomerRepository
from app.db.repositories.quote_document_action_repository import QuoteDocumentActionRepository
from app.integrations.whatsapp_api import send_whatsapp_message
from app.file_access.registry import get_file_provider
from app.monitoring.logger import log
from app.monitoring.audit import audit_event
from app.monitoring.slack_alerts import send_slack_alert
from datetime import datetime, timedelta, timezone
import traceback

MAX_RETRIES = 3
QUOTE_REMINDER_DAYS = 7

async def process_pending_notifications():
    async with SessionLocal() as db:
        repo = NotificationRepository(db)
        tenant_repo = TenantRepository(db)
        notifications = await repo.list_pending_or_retry()
        for notification in notifications:
            try:
                tenant = await tenant_repo.get(notification.tenant_id)
                result = await send_whatsapp_message(notification, tenant)
                if result["success"]:
                    await repo.update(notification.id, status="sent")
                    await audit_event("whatsapp_sent", notification.tenant_id, None, {"notification_id": str(notification.id)})
                else:
                    retries = getattr(notification, "retry_count", 0) + 1
                    status = "retry" if retries < MAX_RETRIES else "failed"
                    await repo.update(notification.id, status=status, retry_count=retries)
                    await audit_event("whatsapp_failed", notification.tenant_id, None, {"notification_id": str(notification.id), "retries": retries})
            except Exception as exc:
                tb = traceback.format_exc()
                log("ERROR", f"Notification retry error: {exc}", module="jobs")
                await audit_event("notification_retry_error", notification.tenant_id, None, {"notification_id": str(notification.id), "error": str(exc), "traceback": tb})
                await send_slack_alert(f"Notification retry error: {exc}", context={"notification_id": str(notification.id), "traceback": tb}, severity="CRITICAL", module="jobs")

async def process_excel_update_queue():
    async with SessionLocal() as db:
        repo = QuoteDocumentActionRepository(db)
        quote_repo = QuoteRepository(db)
        customer_repo = CustomerRepository(db)
        tenant_repo = TenantRepository(db)
        actions = await repo.list_pending()
        for action in actions:
            try:
                quote = await quote_repo.get(action.quote_id)
                customer = await customer_repo.get(quote.customer_id)
                tenant = await tenant_repo.get_by_id(quote.tenant_id)
                
                if tenant and tenant.file_provider:
                    provider = get_file_provider(tenant)
                    customer_dict = {
                        "name": customer.name,
                        "email": customer.email,
                        "phone": customer.phone
                    }
                    result = await provider.update_quote_excel(quote.tenant_id, quote, customer_dict)
                    
                    if result.success:
                        await repo.update(action.id, status="completed")
                        await audit_event("excel_update_completed", quote.tenant_id, quote.flow_id, {"quote_id": str(quote.id), "provider": tenant.file_provider})
                        log("INFO", f"Excel update completed for quote {quote.id}", module="jobs", tenant_id=quote.tenant_id)
                    else:
                        await repo.update(action.id, status="failed")
                        log("ERROR", f"Excel update failed: {result.message}", module="jobs", tenant_id=quote.tenant_id)
                        await audit_event("excel_update_failed", quote.tenant_id, quote.flow_id, {"quote_id": str(quote.id), "error": result.message})
                else:
                    log("WARNING", f"No file provider configured for tenant {quote.tenant_id}", module="jobs", tenant_id=quote.tenant_id)
                    await repo.update(action.id, status="skipped")
                    
            except Exception as exc:
                tb = traceback.format_exc()
                log("ERROR", f"Excel update queue error: {exc}", module="jobs")
                await repo.update(action.id, status="failed")
                await audit_event("excel_update_failed", action.tenant_id, None, {"action_id": str(action.id), "error": str(exc), "traceback": tb})
                await send_slack_alert(f"Excel update queue error: {exc}", context={"action_id": str(action.id), "traceback": tb}, severity="CRITICAL", module="jobs")

async def process_quote_reminders():
    async with SessionLocal() as db:
        quote_repo = QuoteRepository(db)
        customer_repo = CustomerRepository(db)
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(days=QUOTE_REMINDER_DAYS)
        quotes = await quote_repo.list_open_older_than(threshold)
        for quote in quotes:
            try:
                customer = await customer_repo.get(quote.customer_id)
                # Enqueue WhatsApp reminder (reuse enqueue_text_message from whatsapp.py)
                from app.api.notifications.whatsapp import enqueue_text_message
                message = f"Gentile cliente, il suo preventivo è ancora in lavorazione."
                await enqueue_text_message(quote.tenant_id, customer.phone, message)
                await audit_event("quote_reminder_sent", quote.tenant_id, quote.flow_id, {"quote_id": str(quote.id)})
            except Exception as exc:
                tb = traceback.format_exc()
                log("ERROR", f"Quote reminder error: {exc}", module="jobs")
                await audit_event("quote_reminder_error", quote.tenant_id, quote.flow_id, {"quote_id": str(quote.id), "error": str(exc), "traceback": tb})
                await send_slack_alert(f"Quote reminder error: {exc}", context={"quote_id": str(quote.id), "traceback": tb}, severity="CRITICAL", module="jobs")

async def process_daily_health_report():
    # Placeholder for daily health report job
    log("INFO", "Daily health report job executed.", module="jobs")
    await audit_event("daily_health_report", None, None, {"timestamp": datetime.now(timezone.utc).isoformat()})
