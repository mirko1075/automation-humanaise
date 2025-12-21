import base64
import json
import os
import sys
import pytest
from fastapi.testclient import TestClient
import uuid
from sqlalchemy import text, create_engine

# Ensure project root is on sys.path so `app` package imports work when pytest is run
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.main import app
from app.db.session import engine
from app.config import settings

client = TestClient(app)


def make_pubsub_message(historyId: str, emailAddress: str, messageId: str = None):
    payload = {"historyId": historyId, "emailAddress": emailAddress}
    if messageId:
        payload["messageId"] = messageId
    b = base64.b64encode(json.dumps(payload).encode()).decode()
    return {"message": {"data": b}}


def _build_sync_engine():
    url = settings.DATABASE_URL
    if not url:
        return engine.sync_engine
    if "+asyncpg" in url:
        sync_url = url.replace("+asyncpg", "")
    elif "+aiosqlite" in url:
        sync_url = url.replace("+aiosqlite", "")
    else:
        sync_url = url
    return create_engine(sync_url, future=True, echo=False)


sync_test_engine = _build_sync_engine()


@pytest.mark.integration
def test_gmail_webhook_creates_rawevent():
    # Arrange
    history_id = f"itest-hist-{uuid.uuid4()}"
    email = "integration-test@example.com"
    body = make_pubsub_message(history_id, email)

    # Act
    resp = client.post("/gmail/webhook", json=body)

    # Assert HTTP 200 ACK
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") in ("received", "unassigned")

    # Check DB row using a true sync engine (after migrations applied)
    with sync_test_engine.begin() as conn:
        row = conn.execute(text("SELECT id, tenant_id, source, payload, idempotency_key, processed FROM raw_events WHERE payload->>'original' IS NOT NULL ORDER BY created_at DESC LIMIT 1"))
        r = row.first()
        assert r is not None, "No RawEvent row created"
        _id, tenant_id, source, payload, idempotency_key, processed = r
        assert source == 'gmail'
        assert isinstance(payload, dict)
        assert payload.get('channel') == 'email'
        assert payload.get('identifier') == email
        assert payload.get('external_ref') == history_id
        assert payload.get('outcome') in ('received', 'unassigned')
        assert processed in (0, False)
