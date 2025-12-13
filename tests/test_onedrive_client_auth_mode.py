import pytest
from unittest.mock import patch
from app.integrations.onedrive_client import OneDriveClient, TestTokenAuth, OAuthAuth
from app.config import settings

def test_client_uses_test_token_by_default(monkeypatch):
    # Ensure ONEDRIVE_AUTH_MODE=test yields TestTokenAuth
    monkeypatch.setattr(settings, "ONEDRIVE_AUTH_MODE", "test")
    client = OneDriveClient()
    assert isinstance(client.auth, TestTokenAuth)

def test_client_uses_oauth_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "ONEDRIVE_AUTH_MODE", "app")
    # Provide fake env vars for OAuthAuth
    monkeypatch.setattr(settings, "MS_CLIENT_ID", "cid")
    monkeypatch.setattr(settings, "MS_CLIENT_SECRET", "sec")
    monkeypatch.setattr(settings, "MS_TENANT_ID", "tid")
    client = OneDriveClient()
    assert isinstance(client.auth, OAuthAuth)
*** End Patch