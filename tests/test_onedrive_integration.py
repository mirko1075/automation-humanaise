# tests/test_onedrive_integration.py
"""
Unit tests for OneDrive integration helpers.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.integrations import onedrive_api as onedrive
from app.db.session import SessionLocal, Base, engine
from sqlalchemy import text


class MockQuote:
    def __init__(self):
        self.id = "quote-123"
        self.tenant_id = "test-tenant"
        self.flow_id = "preventivi_v1"
        self.external_reference = None
        self.quote_data = {"descrizione_lavori": "test job"}
        self.status = "pending"
        self.created_at = datetime.now(timezone.utc)


@pytest_asyncio.fixture
async def db_setup():
    # Ensure tables exist for test DB
    if str(engine.url).startswith("sqlite"):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.mark.asyncio
async def test_update_alias_and_successful_post(db_setup, monkeypatch):
    quote = MockQuote()
    customer = MagicMock()
    customer.name = "Mario"
    customer.email = "mario@example.com"
    customer.phone = "+391234"

    # Create a fake client that supports async context manager for get/post/patch
    class FakeResp:
        def __init__(self, status=200, payload=None):
            self.status = status
            self._payload = payload or {"value": []}

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status >= 400:
                raise Exception("HTTP Error")

    class FakeClient:
        def __init__(self):
            pass

        def get(self, url):
            return FakeResp(payload={"value": []})

        def post(self, url, json=None):
            return FakeResp(payload={"id": "newrow"})

        def patch(self, url, json=None):
            return FakeResp(payload={"id": "updated"})

    # Patch get_graph_client to return our FakeClient
    monkeypatch.setattr(onedrive, "get_graph_client", AsyncMock(return_value=FakeClient()))

    # Patch audit_event, log, and send_slack_alert to avoid side effects
    mock_audit = AsyncMock()
    monkeypatch.setattr(onedrive, "audit_event", mock_audit)
    monkeypatch.setattr(onedrive, "log", lambda *args, **kwargs: None)
    monkeypatch.setattr(onedrive, "send_slack_alert", AsyncMock())

    # Call via alias to ensure compatibility name works
    await onedrive.update_excel_on_onedrive("test-tenant", quote, customer)

    # Assert audit_event called for successful update
    mock_audit.assert_awaited()
    # The successful call should include the 'onedrive_excel_updated' event
    called = any(call.args and call.args[0] == "onedrive_excel_updated" for call in mock_audit.await_args_list)
    assert called, "Expected audit_event to be called with 'onedrive_excel_updated'"


@pytest.mark.asyncio
async def test_enqueue_excel_update_creates_action(db_setup):
    quote = MockQuote()

    # Ensure DB is clean and tables exist
    async with SessionLocal() as db:
        # Remove any existing entries (best-effort)
        await db.execute(text("DELETE FROM quote_document_actions"))
        await db.commit()

    # Patch audit_event to avoid DB writes from audit
    from unittest.mock import AsyncMock
    onedrive.audit_event = AsyncMock()

    # Call enqueue
    await onedrive.enqueue_excel_update(quote)

    # Verify action exists
    async with SessionLocal() as db:
        res = await db.execute(text("SELECT id, tenant_id, quote_id, status FROM quote_document_actions"))
        rows = res.fetchall()
        assert len(rows) >= 1
        assert rows[0][1] == str(quote.tenant_id)
        assert rows[0][2] == str(quote.id)
        assert rows[0][3] == "PENDING"

    # Verify audit_event was called for enqueue
    assert onedrive.audit_event.await_count >= 1


@pytest.mark.asyncio
async def test_update_error_path_calls_audit_and_alert(monkeypatch):
    """Simulate Graph API failure and assert audit_event and slack alert are called."""
    quote = MockQuote()
    customer = MagicMock()
    customer.name = "Mario"
    customer.email = "mario@example.com"
    customer.phone = "+391234"

    # Create a client whose get raises an exception
    class BadClient:
        def get(self, url):
            raise Exception("Network error")

    monkeypatch.setattr(onedrive, "get_graph_client", AsyncMock(return_value=BadClient()))

    mock_audit = AsyncMock()
    mock_alert = AsyncMock()
    monkeypatch.setattr(onedrive, "audit_event", mock_audit)
    monkeypatch.setattr(onedrive, "send_slack_alert", mock_alert)
    monkeypatch.setattr(onedrive, "log", lambda *args, **kwargs: None)

    # Call and expect it to handle exception (no raise)
    await onedrive.update_quote_excel("test-tenant", quote, customer)

    # audit_event should have been called with an 'onedrive_error' event
    assert any(call.args and call.args[0] == "onedrive_error" for call in mock_audit.await_args_list)
    # Slack alert should have been triggered
    assert mock_alert.await_count >= 1
