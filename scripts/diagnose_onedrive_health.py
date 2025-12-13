import os
import asyncio
from fastapi.testclient import TestClient

# Ensure the project package is importable
import sys
sys.path.insert(0, '.')

# Set necessary env vars
os.environ['MS_DRIVE_ID'] = 'test-drive-id'
os.environ['ONEDRIVE_HEALTHCHECK_WRITE'] = 'true'

from app.main import app
import app.integrations.onedrive_client as onedrive_client_module
import app.api.admin.health as health_module

class DummyClientWrite:
    def __init__(self):
        class Auth:
            async def _ensure_token(self):
                return None
        self.auth = Auth()
    async def get_drive(self, drive_id):
        return {'id': drive_id}
    async def get_drive_root(self, drive_id):
        return {'id': 'root'}
    async def list_drive_root_children(self, drive_id):
        return {'value': []}
    async def create_folder(self, drive_id, parent_item_id='root', name='_healthcheck'):
        return {'id': 'created'}
    async def delete_item(self, drive_id, item_id):
        return None

# Patch both symbols
onedrive_client_module.OneDriveClient = lambda: DummyClientWrite()
health_module.OneDriveClient = lambda: DummyClientWrite()

client = TestClient(app)
resp = client.get('/admin/health/onedrive')
print('status_code=', resp.status_code)
print('body=', resp.json())
