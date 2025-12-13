import os
from fastapi.testclient import TestClient
from app.main import app
import pytest


class DummyClientWrite:
    def __init__(self):
        class Auth:
            async def _ensure_token(self):
                return None

        self.auth = Auth()
import os
from fastapi.testclient import TestClient
from app.main import app
import pytest


class DummyClientWrite:
    def __init__(self):
        self.auth = type("A", (), {"_ensure_token": lambda: None})()

    async def get_drive(self, drive_id):
        return {"id": drive_id}

    async def get_drive_root(self, drive_id):
        import os
        from fastapi.testclient import TestClient
        from app.main import app
        import pytest


        class DummyClientWrite:
            def __init__(self):
                class Auth:
                    async def _ensure_token(self):
                        return None

                self.auth = Auth()

            async def get_drive(self, drive_id):
                return {"id": drive_id}

            async def get_drive_root(self, drive_id):
                return {"id": "root"}

            async def list_drive_root_children(self, drive_id):
                return {"value": []}

            async def create_folder(self, drive_id, parent_item_id="root", name="_healthcheck"):
                return {"id": "created"}

            async def delete_item(self, drive_id, item_id):
                return None


        @pytest.fixture(autouse=True)
        def env_ms_drive_id(monkeypatch):
            monkeypatch.setenv("MS_DRIVE_ID", "test-drive-id")
            # Enable write test
            monkeypatch.setenv("ONEDRIVE_HEALTHCHECK_WRITE", "true")
            yield


        def test_onedrive_health_write_mode(monkeypatch):
            # Apply direct assignment for test determinism in pytest environment
            import app.integrations.onedrive_client as onedrive_client_module
            import app.api.admin.health as health_module
            onedrive_client_module.OneDriveClient = DummyClientWrite
            health_module.OneDriveClient = DummyClientWrite

            client = TestClient(app)
            resp = client.get('/admin/health/onedrive')
            assert resp.status_code == 200
            body = resp.json()
            assert body['status'] == 'ok', f"onedrive health failed: {body}"
            assert body['steps']['write']['ok'] is True