import asyncio
import pytest

from fastapi.testclient import TestClient

from app.main import app


class FakeAuth:
    async def _ensure_token(self):
        return


class FakeClientSuccess:
    def __init__(self):
        self.auth = FakeAuth()

    async def get_drive(self, drive_id):
        return {"id": drive_id, "driveType": "business"}

    async def get_drive_root(self, drive_id):
        return {"id": "rootid"}

    async def list_drive_root_children(self, drive_id):
        return {"value": []}

    async def create_folder(self, drive_id, parent_item_id="root", name="_healthcheck"):
        return {"id": "tempid"}

    async def delete_item(self, drive_id, item_id):
        return None


class FakeClientAccessDenied(FakeClientSuccess):
    async def get_drive(self, drive_id):
        raise RuntimeError("Get drive failed: 403 Access denied")


@pytest.fixture(autouse=True)
def client_env(monkeypatch):
    # ensure tests use app test client
    yield


def test_onedrive_health_success(monkeypatch):
    # Patch OneDriveClient constructor to return fake successful client
    from app.integrations.onedrive_client import OneDriveClient

    monkeypatch.setattr('app.integrations.onedrive_client.OneDriveClient', lambda: FakeClientSuccess())
    client = TestClient(app)
    resp = client.get('/admin/health/onedrive')
    assert resp.status_code == 200
    body = resp.json()
    assert body['status'] == 'ok'
    steps = body['steps']
    assert steps['auth']['ok'] is True
    assert steps['drive']['ok'] is True
    assert steps['root']['ok'] is True
    assert steps['children']['ok'] is True


def test_onedrive_health_access_denied(monkeypatch):
    monkeypatch.setattr('app.integrations.onedrive_client.OneDriveClient', lambda: FakeClientAccessDenied())
    client = TestClient(app)
    resp = client.get('/admin/health/onedrive')
    # Should return 200 with status fail inside body
    assert resp.status_code == 200
    body = resp.json()
    assert body['status'] == 'fail'
    assert body['steps']['drive']['ok'] is False
    assert 'error' in body['steps']['drive']
