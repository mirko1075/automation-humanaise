import pytest

from fastapi.testclient import TestClient

from app.main import app


class FakeAuth:
    async def _ensure_token(self):
        return


class FakeClientOK:
    def __init__(self):
        self.auth = FakeAuth()

    async def get_drive(self, drive_id):
        return {"id": drive_id}

    async def get_drive_root(self, drive_id):
        return {"id": "rootid"}

    async def list_drive_root_children(self, drive_id):
        return {"value": []}


class FakeClientFail(FakeClientOK):
    async def get_drive(self, drive_id):
        raise RuntimeError("Access denied")


def test_admin_ready_onedrive_ok(monkeypatch):
    monkeypatch.setattr('app.integrations.onedrive_client.OneDriveClient', lambda: FakeClientOK())
    async def _db_ready():
        return True
    monkeypatch.setattr('app.api.admin.health.check_db_ready', _db_ready)
    client = TestClient(app)
    resp = client.get('/admin/ready')
    assert resp.status_code == 200
    assert resp.json().get('status') == 'ready'


def test_admin_ready_onedrive_fail(monkeypatch):
    monkeypatch.setattr('app.integrations.onedrive_client.OneDriveClient', lambda: FakeClientFail())
    async def _db_ready():
        return True
    monkeypatch.setattr('app.api.admin.health.check_db_ready', _db_ready)
    client = TestClient(app)
    resp = client.get('/admin/ready')
    assert resp.status_code == 503
    body = resp.json()
    assert isinstance(body.get('detail'), dict)
    assert body['detail'].get('reason') in ('onedrive_not_ready', 'onedrive_check_failed')
