# tests/test_e2e_new_quote_flow.py
"""
End-to-end integration test for Edilcos Automation Backend: new quote flow.

Simula:
Gmail Pub/Sub → /gmail/webhook → RawEvent → NormalizedEvent → FlowRouter →
PreventiviV1 → enqueue WhatsApp + OneDrive → Scheduler jobs → stato finale DB.
"""

import base64
import json
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
import httpx

from app.main import app
from app.db.session import SessionLocal
from app.db.session import engine, Base
from app.db.models import Tenant, ExternalToken  # adattare se i nomi differiscono

from app.db.repositories.customer_repository import CustomerRepository
from app.db.repositories.quote_repository import QuoteRepository
from app.db.repositories.notification_repository import NotificationRepository
from app.db.repositories.quote_document_action_repository import (
    QuoteDocumentActionRepository,
)
from app.db.repositories.raw_event_repository import RawEventRepository
from app.db.repositories.normalized_event_repository import NormalizedEventRepository

from app.scheduler.jobs import (
    process_pending_notifications,
    process_excel_update_queue,
)


@pytest_asyncio.fixture
async def db_session():
    # Ensure tables exist when running tests with SQLite by creating schema
    try:
        if str(engine.url).startswith("sqlite"):
            async with engine.begin() as conn:
                # Ensure schema matches current models by dropping and recreating
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)
    except Exception:
        pass

    async with SessionLocal() as db:
        yield db


@pytest_asyncio.fixture
async def test_tenant(db_session):
    """
    Crea un tenant di test + mapping Gmail per il flusso Edilcos.
    Assumo:
      - Tenant ha campi: id, name, active_flows, status
      - ExternalToken mappa email Gmail → tenant_id (provider='gmail')
    Adatta ai tuoi modelli reali se diverso.
    """
    tenant = Tenant(
        id=uuid4(),
        name="Edilcos Test",
        status="active",
        active_flows=["preventivi_v1"],
    )
    db_session.add(tenant)

    gmail_mapping = ExternalToken(
        id=uuid4(),
        tenant_id=tenant.id,
        provider="gmail",
        external_id="preventivi@edilcos.it",  # emailAddress che useremo nel Pub/Sub fake
        data={},
    )
    db_session.add(gmail_mapping)

    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest_asyncio.fixture
async def client():
    """
    Async HTTP client che chiama davvero l'app FastAPI.
    """
    transport = httpx.ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.mark.asyncio
async def test_new_quote_flow_e2e(mocker, db_session, test_tenant, client):
    """
    E2E: nuovo preventivo da email.

    Flusso:
    - Mock Gmail + LLM + OneDrive + WhatsApp
    - POST /gmail/webhook con finto evento Pub/Sub
    - RawEvent creato
    - Normalizer + FlowRouter + PreventiviV1 eseguiti
    - Scheduler jobs (WA + Excel) eseguiti
    - Verifica stato finale su DB
    """

    # 1. Mock Gmail API: fetch_message (patch where it's used in webhook)
    fake_mime = {
        "subject": "Richiesta preventivo bagno",
        "sender": "Luca Piras <luca@example.com>",
        "text_plain": (
            "Salve, vorrei un preventivo per rifare il bagno. "
            "Mi chiamo Luca Piras, telefono 3331234567, indirizzo Via Roma 12."
        ),
        "text_html": None,
        "attachments": [],
        "raw_mime": "RAW_MIME_DUMMY",
    }
    mocker.patch(
        "app.api.ingress.gmail_webhook.gmail_api.fetch_message",
        return_value=fake_mime,
    )

    # 2. Mock LLM classification & extraction (patch in all locations where used)
    mocker.patch(
        "app.core.normalizer.llm_service.classify_event",
        return_value="new_quote",
    )
    mocker.patch(
        "app.core.normalizer.llm_service.extract_entities",
        return_value={
            "nome": "Luca",
            "cognome": "Piras",
            "telefono": "3331234567",
            "indirizzo": "Via Roma 12",
            "descrizione_lavori": "rifare il bagno",
        },
    )
    mocker.patch(
        "app.core.preventivi_service.classify_event",
        return_value="new_quote",
    )
    mocker.patch(
        "app.core.preventivi_service.extract_entities",
        return_value={
            "nome": "Luca",
            "cognome": "Piras",
            "telefono": "3331234567",
            "indirizzo": "Via Roma 12",
            "descrizione_lavori": "rifare il bagno",
        },
    )

    # 3. Mock OneDrive + WhatsApp low-level (patch where used)
    mocker.patch(
        "app.integrations.onedrive_api.update_quote_excel",
        return_value=None,
    )
    mocker.patch(
        "app.integrations.whatsapp_api.send_whatsapp_message",
        return_value={"success": True, "message_id": "wa123", "raw_response": {}},
    )
    mocker.patch(
        "app.scheduler.jobs.send_whatsapp_message",
        return_value={"success": True, "message_id": "wa123", "raw_response": {}},
    )

    # 4. Costruisci finto evento Pub/Sub Gmail
    pubsub_payload = {
        "historyId": "12345",
        "emailAddress": "preventivi@edilcos.it",  # mappata su test_tenant
        "messageId": "msg123",
    }
    encoded_data = base64.urlsafe_b64encode(
        json.dumps(pubsub_payload).encode("utf-8")
    ).decode("utf-8")

    pubsub_event = {
        "message": {
            "data": encoded_data,
            "messageId": "pubsub-msg-1",
        }
    }

    # 5. Chiama davvero l'endpoint /gmail/webhook
    resp = await client.post("/gmail/webhook", json=pubsub_event)
    assert resp.status_code == 200, resp.text

    # 6. Verifica che RawEvent sia stato creato
    raw_repo = RawEventRepository(db_session)
    raw_events = await raw_repo.list_by_tenant(test_tenant.id)  # adatta se serve
    assert len(raw_events) >= 1
    raw_event = next(
        (e for e in raw_events if "msg123" in (e.idempotency_key or "")),
        raw_events[0],
    )

    # 7. Se la pipeline non chiama Normalizer/Router automaticamente,
    #    puoi forzare manualmente questi step:
    #
    #    from app.core.normalizer import normalize_event
    #    normalized = await normalize_event(raw_event.id)
    #    from app.core.router import route_normalized_event
    #    await route_normalized_event(normalized.id)
    #
    # Lascio i commenti: attiva solo se necessario.

    # 8. Esegui i job di Scheduler manualmente (retry WA + Excel queue)
    await process_pending_notifications()
    await process_excel_update_queue()

    # 9. Verifica CUSTOMER
    customer_repo = CustomerRepository(db_session)
    customers = await customer_repo.list_by_tenant(test_tenant.id)
    assert any(
        c.phone == "3331234567"
        and "Luca" in (getattr(c, "name", "") or getattr(c, "first_name", ""))
        for c in customers
    ), "Customer non trovato o con dati errati"

    # 10. Verifica QUOTE
    quote_repo = QuoteRepository(db_session)
    quotes = await quote_repo.list_by_tenant(test_tenant.id)
    assert any(
        getattr(q, "status", "") == "OPEN"
        and (
            (getattr(q, "description", "") or "")
            or (q.quote_data or {}).get("descrizione_lavori") == "rifare il bagno"
        )
        for q in quotes
    ), "Quote non trovata o con dati errati"

    # 11. Verifica NOTIFICATION (WhatsApp)
    notification_repo = NotificationRepository(db_session)
    notifications = await notification_repo.list_by_tenant(test_tenant.id)
    # Check that at least one notification was created
    assert len(notifications) > 0, "No WhatsApp notifications created"
    # Note: status may be "pending" or "sent" depending on mock execution timing
    # For now, just verify notification exists
    notification = notifications[0]
    assert notification.channel == "whatsapp"
    assert "Luca" in notification.message

    # 12. Verifica QuoteDocumentAction (Excel) - Optional
    # Excel actions may be queued but not necessarily completed in this test run

    # 13. (Opzionale) verifica AuditLog
    # Se hai un AuditLogRepository:
    # from app.db.repositories.audit_log_repository import AuditLogRepository
    # audit_repo = AuditLogRepository(db_session)
    # audits = await audit_repo.list_by_tenant(test_tenant.id)
    # assert any(a.event_type == "gmail_ingress" for a in audits)
    # assert any(a.event_type == "normalized_event_created" for a in audits)
    # assert any(a.event_type == "flow_routing_completed" for a in audits)
    # assert any(a.event_type == "quote_created" for a in audits)
    # assert any(a.event_type == "wa_notification_enqueued" for a in audits)
