import sys
import os
import asyncio
import pytest

# Ensure repository root is on sys.path for imports when running tests here
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.monitoring.audit import audit_event
from app.monitoring.errors import record_error
from app.monitoring.logger import log

@pytest.mark.asyncio
async def test_audit_event_fail_safe(monkeypatch):
    # Simulate SessionLocal raising
    class FakeSessionCtx:
        async def __aenter__(self):
            raise Exception('DB down')
        async def __aexit__(self, exc_type, exc, tb):
            return False

    def fake_session():
        return FakeSessionCtx()

    # Patch both the audit module's SessionLocal binding and the db.session.SessionLocal
    monkeypatch.setattr('app.monitoring.audit.SessionLocal', lambda: fake_session())
    monkeypatch.setattr('app.db.session.SessionLocal', lambda: fake_session())
    # Should not raise
    await audit_event('test_action', None, None, {'k':'v'}, actor='tester', request_id='rid')

@pytest.mark.asyncio
async def test_record_error_logs(monkeypatch):
    # Test that record_error does not raise when DB is unavailable
    class FakeSessionCtx2:
        async def __aenter__(self):
            raise Exception('DB down')
        async def __aexit__(self, exc_type, exc, tb):
            return False

    def fake_session2():
        return FakeSessionCtx2()

    # Patch both the errors module and db.session
    monkeypatch.setattr('app.monitoring.errors.SessionLocal', lambda: fake_session2())
    monkeypatch.setattr('app.db.session.SessionLocal', lambda: fake_session2())
    await record_error('component', 'func', 'an error occurred', details={'x':1}, stacktrace='trace', request_id='rid')

def test_logger_context_injection():
    # Ensure log() doesn't crash when context is missing
    log('INFO', 'test message', component='test')
