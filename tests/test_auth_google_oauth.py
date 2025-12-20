import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app
from app.config import settings


def test_google_login_redirect(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "https://example.com/auth/google/callback")

    client = TestClient(app)
    resp = client.get("/auth/google/login?tenant_id=test-tenant", follow_redirects=False)
    assert resp.status_code == 307 or resp.status_code == 302
    assert "accounts.google.com" in resp.headers["location"]
    assert "scope=" in resp.headers["location"]


@pytest.mark.asyncio
async def test_google_callback_persists_tokens(monkeypatch):
    # Setup env
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "https://example.com/auth/google/callback")

    # Mock httpx AsyncClient.post to return token payload
    token_payload = {"access_token": "at", "refresh_token": "rt", "expires_in": 3600, "id_token": "eyJhbGci..."}

    class DummyResp:
        def __init__(self, json_data):
            self._json = json_data

        def raise_for_status(self):
            return None

        def json(self):
            return self._json

    async def dummy_post(*args, **kwargs):
        return DummyResp(token_payload)

    # Patch httpx.AsyncClient.post
    monkeypatch.setattr("httpx.AsyncClient.post", lambda *args, **kwargs: dummy_post(*args, **kwargs))

    # Patch ExternalTokenRepository to record calls
    from app.db.repositories.external_token_repository import ExternalTokenRepository

    async def fake_list_by_tenant(self, tenant_id):
        return []

    async def fake_list_by_external_id(self, external_id):
        return []

    async def fake_update(self, token_id, **kwargs):
        return None

    monkeypatch.setattr(ExternalTokenRepository, "list_by_tenant", fake_list_by_tenant)
    monkeypatch.setattr(ExternalTokenRepository, "list_by_external_id", fake_list_by_external_id)
    monkeypatch.setattr(ExternalTokenRepository, "update", fake_update)

    client = TestClient(app)
    # Simulate callback with code and state containing tenant_id
    import base64, json
    state = base64.urlsafe_b64encode(json.dumps({"tenant_id": "test-tenant"}).encode()).decode()
    resp = client.get(f"/auth/google/callback?code=abc123&state={state}")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("status") == "success"
    assert body.get("tenant_id") == "test-tenant"
