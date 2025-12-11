import sys
from types import SimpleNamespace

# Provide a richer aiohttp module stub for tests to avoid DNS/aiodns issues
class _Resp:
    def __init__(self, status=200, json_data=None):
        self.status = status
        self._json = json_data or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self):
        return self._json

    def raise_for_status(self):
        return None


class _ClientSession:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def get(self, *args, **kwargs):
        return _Resp()

    def post(self, *args, **kwargs):
        return _Resp()


aiohttp_stub = SimpleNamespace()
aiohttp_stub.ClientSession = _ClientSession
aiohttp_stub.web = SimpleNamespace()

sys.modules.setdefault('aiohttp', aiohttp_stub)
sys.modules.setdefault('aiohttp.client', aiohttp_stub)
sys.modules.setdefault('aiohttp.web', aiohttp_stub)
