import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from app.integrations.onedrive_client import OAuthAuth

@pytest.mark.asyncio
async def test_oauth_token_acquisition(monkeypatch):
    # Mock aiohttp.ClientSession.post to return a fake token response
    fake_resp = AsyncMock()
    fake_resp.status = 200
    fake_resp.json = AsyncMock(return_value={"access_token": "abc123", "expires_in": 3600})
    class FakeCtx:
        def __init__(self, resp):
            self._resp = resp
        async def __aenter__(self):
            return self._resp
        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeSession:
        def __init__(self):
            pass
        def post(self, url, data=None):
            return FakeCtx(fake_resp)
        async def close(self):
            return None

    oauth = OAuthAuth(client_id="cid", client_secret="secret", tenant_id="tid", session=FakeSession())
    headers = await oauth.get_auth_headers()
    assert "Authorization" in headers
    assert headers["Authorization"].startswith("Bearer ")

@pytest.mark.asyncio
async def test_oauth_refresh(monkeypatch):
    calls = []
    fake_resp1 = AsyncMock()
    fake_resp1.status = 200
    fake_resp1.json = AsyncMock(return_value={"access_token": "token1", "expires_in": 1})

    fake_resp2 = AsyncMock()
    fake_resp2.status = 200
    fake_resp2.json = AsyncMock(return_value={"access_token": "token2", "expires_in": 3600})

    class FakeCtx:
        def __init__(self, resp):
            self._resp = resp
        async def __aenter__(self):
            return self._resp
        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeSession:
        def __init__(self):
            self._i = 0
        def post(self, url, data=None):
            self._i += 1
            if self._i == 1:
                return FakeCtx(fake_resp1)
            return FakeCtx(fake_resp2)
        async def close(self):
            return None

    oauth = OAuthAuth(client_id="cid", client_secret="secret", tenant_id="tid", session=FakeSession())
    h1 = await oauth.get_auth_headers()
    assert "token1" in h1["Authorization"]
    # wait for token to expire (expires_in was 1s)
    await asyncio.sleep(1.1)
    h2 = await oauth.get_auth_headers()
    assert "token2" in h2["Authorization"]