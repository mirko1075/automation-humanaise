import pytest
import asyncio
from unittest.mock import AsyncMock
from app.integrations.onedrive_client import OAuthAuth, OneDriveClient
from app.config import settings

@pytest.mark.asyncio
async def test_missing_env_vars_fail_startup(monkeypatch):
    # Temporarily set mode to app and clear credentials
    monkeypatch.setattr(settings, "ONEDRIVE_AUTH_MODE", "app")
    monkeypatch.setattr(settings, "MS_CLIENT_ID", None)
    monkeypatch.setattr(settings, "MS_CLIENT_SECRET", None)
    monkeypatch.setattr(settings, "MS_TENANT_ID", None)
    with pytest.raises(RuntimeError):
        # Attempting to instantiate OAuthAuth and calling get_auth_headers should fail
        oa = OAuthAuth(client_id=None, client_secret=None, tenant_id=None, session=AsyncMock())
        await oa.get_auth_headers()

@pytest.mark.asyncio
async def test_token_endpoint_failure(monkeypatch):
    class FailSession:
        def post(self, url, data=None):
            class Ctx:
                async def __aenter__(self):
                    class Resp:
                        status = 500
                        async def text(self):
                            return "internal error"
                    return Resp()
                async def __aexit__(self, exc_type, exc, tb):
                    return False
            return Ctx()
        async def close(self):
            return None

    oa = OAuthAuth(client_id="cid", client_secret="secret", tenant_id="tid", session=FailSession())
    with pytest.raises(RuntimeError):
        await oa.get_auth_headers()

@pytest.mark.asyncio
async def test_graph_403_propagates(monkeypatch):
    # Mock OneDriveClient to use a fake session that returns 403 on list_files
    class Resp403:
        status = 403
        async def text(self):
            return "forbidden"
    class FakeCtx:
        async def __aenter__(self):
            return Resp403()
        async def __aexit__(self, exc_type, exc, tb):
            return False
    class FakeSession:
        def get(self, url):
            return FakeCtx()
        async def close(self):
            return None

    client = OneDriveClient(session=FakeSession())
    with pytest.raises(RuntimeError):
        await client.list_files("some/path")
*** End Patch