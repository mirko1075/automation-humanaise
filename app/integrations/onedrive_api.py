# app/integrations/onedrive_api.py
"""
OneDriveConnector for Edilcos Automation Backend.
Handles Excel updates for quotes via Microsoft Graph API.
"""
from typing import Dict, Optional, Any
from uuid import UUID
from app.db.models import Quote, Customer
from app.monitoring.logger import log
from app.monitoring.audit import audit_event
from app.monitoring.slack_alerts import send_slack_alert
from app.config import settings
from app.db.session import SessionLocal
from datetime import datetime
import traceback
# aiohttp is imported lazily inside async functions to avoid import-time
# failures when optional networking dependencies (aiodns/pycares) are missing

# Queue model for Excel update actions
from sqlalchemy import Column, String, DateTime, JSON
from app.db.session import Base

class QuoteDocumentAction(Base):
    __tablename__ = "quote_document_actions"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    quote_id = Column(String, nullable=False)
    action_type = Column(String, nullable=False, default="excel_update")
    payload = Column(JSON, nullable=False)
    status = Column(String, nullable=False, default="PENDING")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

async def get_graph_client() -> Any:
    """
    Get an authenticated Microsoft Graph client session.
    """
    # Acquire token using client credentials
    import aiohttp

    token_url = f"https://login.microsoftonline.com/{settings.ONEDRIVE_TENANT_ID}/oauth2/v2.0/token"
    data = {
        "client_id": settings.ONEDRIVE_CLIENT_ID,
        "client_secret": settings.ONEDRIVE_CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(token_url, data=data) as resp:
            resp.raise_for_status()
            token_data = await resp.json()
            access_token = token_data["access_token"]
    return aiohttp.ClientSession(headers={"Authorization": f"Bearer {access_token}"})

async def update_quote_excel(tenant_id: UUID, quote: Quote, customer: Customer) -> None:
    """
    Update the central Excel sheet for a quote via Microsoft Graph API.
    """
    request_id = None
    try:
        client = await get_graph_client()
        # Load Excel file
        excel_url = f"https://graph.microsoft.com/v1.0/drives/{settings.ONEDRIVE_DRIVE_ID}/items/{settings.ONEDRIVE_EXCEL_FILE_ID}/workbook/worksheets('Preventivi')/tables('Quotes')/rows"
        async with client.get(excel_url) as resp:
            resp.raise_for_status()
            rows = await resp.json()
        # Row matching logic
        match_row = None
        for row in rows.get("value", []):
            if quote.external_reference and row["values"][0] == quote.external_reference:
                match_row = row
                break
            elif str(quote.id) == row["values"][0]:
                match_row = row
                break
        # Prepare row data
        row_data = [
            str(quote.id),
            customer.name,
            customer.phone,
            customer.email,
            quote.quote_data.get("descrizione_lavori", ""),
            quote.status,
            datetime.utcnow().isoformat()
        ]
        if match_row:
            # Update existing row
            update_url = f"{excel_url}/{match_row['id']}"
            async with client.patch(update_url, json={"values": [row_data]}) as resp:
                resp.raise_for_status()
        else:
            # Create new row
            async with client.post(excel_url, json={"values": [row_data]}) as resp:
                resp.raise_for_status()
        await audit_event("onedrive_excel_updated", tenant_id, quote.flow_id, {"quote_id": str(quote.id)}, request_id=request_id)
        log("INFO", f"Excel updated for quote {quote.id}", module="onedrive_api", tenant_id=tenant_id)
    except Exception as exc:
        tb = traceback.format_exc()
        log("ERROR", f"OneDrive Excel update error: {exc}", module="onedrive_api", tenant_id=str(tenant_id))
        await audit_event("onedrive_error", str(tenant_id), getattr(quote, "flow_id", None), {"quote_id": str(quote.id), "error": str(exc), "traceback": tb}, request_id=request_id)
        await send_slack_alert(
            message=f"OneDrive Excel update error: {exc}",
            context={"quote_id": str(quote.id), "tenant_id": str(tenant_id), "traceback": tb},
            severity="CRITICAL",
            module="onedrive_api",
            request_id=request_id
        )

async def enqueue_excel_update(quote: Quote) -> None:
    """
    Enqueue an Excel update action for a quote.
    """
    from uuid import uuid4
    async with SessionLocal() as db:
        action = QuoteDocumentAction(
            id=str(uuid4()),  # Generate new ID for action
            tenant_id=str(quote.tenant_id),
            quote_id=str(quote.id),
            payload={"quote_id": str(quote.id)},
            status="PENDING"
        )
        db.add(action)
        await db.commit()
        await db.refresh(action)
        log("INFO", f"Excel update enqueued for quote {quote.id}", module="onedrive_api")
        await audit_event("onedrive_excel_enqueued", str(quote.tenant_id), getattr(quote, "flow_id", None), {"quote_id": str(quote.id)})
        log("INFO", f"Excel update enqueued for quote {quote.id}", module="onedrive_api", tenant_id=str(quote.tenant_id))

async def process_excel_update_queue() -> None:
    """
    Placeholder for processing Excel update queue (to be scheduled).
    """
    # To be implemented in scheduler jobs
    pass


class OneDriveConnector:
    """High-level helper used by services to enqueue OneDrive excel updates."""
    def __init__(self):
        pass

    async def enqueue_excel_update(self, quote: Quote) -> None:
        await enqueue_excel_update(quote)


# Compatibility alias: older code expects `update_excel_on_onedrive`
# Map it to the current implementation `update_quote_excel`.
update_excel_on_onedrive = update_quote_excel

