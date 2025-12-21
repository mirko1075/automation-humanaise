import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app


class DummyClientSuccess:
    async def get_drive(self, drive_id):
        return {"id": drive_id, "driveType": "business"}

    async def get_drive_root(self, drive_id):
        return {"id": "root"}

    async def list_drive_root_children(self, drive_id):
        return {"value": []}

    async def create_folder(self, drive_id, parent_item_id="root", name="_healthcheck"):
        return {"id": "new-folder-id"}

    async def delete_item(self, drive_id, item_id):
        return None


class DummyClientAccessDenied(DummyClientSuccess):
    async def get_drive(self, drive_id):
        raise RuntimeError("403 Forbidden: access denied")


@pytest.fixture(autouse=True)
def env_ms_drive_id(monkeypatch):
    monkeypatch.setenv("MS_DRIVE_ID", "test-drive-id")
    yield


def test_onedrive_health_success(monkeypatch):
    # Replace OneDriveClient with dummy success client
    from app.api.admin import health as health_mod

    monkeypatch.setattr(health_mod, "OneDriveClient", lambda: DummyClientSuccess())

    client = TestClient(app)
    resp = client.get("/admin/health/onedrive")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["steps"]["auth"]["ok"] is True
    assert data["steps"]["drive"]["ok"] is True


def test_onedrive_health_access_denied(monkeypatch):
    from app.api.admin import health as health_mod

    monkeypatch.setattr(health_mod, "OneDriveClient", lambda: DummyClientAccessDenied())

    client = TestClient(app)
    resp = client.get("/admin/health/onedrive")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "fail"
    assert data["steps"]["drive"]["ok"] is False
    assert "access denied" in data["steps"]["drive"]["error"].lower()
