import os
import json
import base64
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app

client = TestClient(app)


def _encode_state(d: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(d).encode()).decode()


def test_google_login_redirect(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "https://example.com/auth/google/callback")

    resp = client.get("/auth/google/login?tenant_id=11111111-1111-1111-1111-111111111111", follow_redirects=False)
    assert resp.status_code == 307 or resp.status_code == 302
    loc = resp.headers.get("location")
    assert "accounts.google.com" in loc
    assert "scope=" in loc


@pytest.mark.asyncio
async def test_google_callback_persists_token(monkeypatch):
    # Prepare env
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "https://example.com/auth/google/callback")

    # Mock httpx.AsyncClient.post to return fake token data
    fake_token = {
        "access_token": "ya29.test",
        "refresh_token": "1//0g-refresh",
        "expires_in": 3600,
        "id_token": None
    }

    class FakeResp:
        def __init__(self, json_data):
            self._json = json_data

        def raise_for_status(self):
            return None

        def json(self):
            return self._json

    async def fake_post(self, url, data=None, headers=None, timeout=None):
        return FakeResp(fake_token)

    # Patch httpx.AsyncClient.post
    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    # Patch ExternalTokenRepository to capture create/update calls
    called = {}

    class DummyRepo:
        def __init__(self, db):
            pass

        async def list_by_tenant(self, tenant_id):
            return []

        async def list_by_external_id(self, external_id):
            return []

        async def create(self, tenant_id, flow_id, provider, token, external_id=None, data=None):
            called['created'] = True
            called['tenant_id'] = tenant_id
            called['provider'] = provider
            called['token'] = token
            called['data'] = data
            return True

        async def update(self, token_id, **kwargs):
            called['updated'] = True
            return True

    monkeypatch.setattr("app.api.auth.google_oauth.ExternalTokenRepository", lambda db: DummyRepo(db))

    # craft a state with tenant_id
    state = _encode_state({"tenant_id": "11111111-1111-1111-1111-111111111111"})

    resp = client.get(f"/auth/google/callback?code=testcode&state={state}")
    assert resp.status_code == 200
    j = resp.json()
    assert j.get("status") == "success"
    assert called.get('created') is True
