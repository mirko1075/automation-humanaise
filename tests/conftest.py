import os
import sys
import pytest
# Ensure project root is on sys.path when pytest imports conftest
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from app.db.session import engine
from app.db.session import Base
from sqlalchemy import text


@pytest.fixture(scope="session", autouse=True)
def create_test_database_schema():
    """Create all tables synchronously using the engine's sync_engine before tests.

    This avoids attaching futures to different event loops when tests run
    using asyncpg/async engines.
    """
    try:
        sync_engine = engine.sync_engine
        # Ensure tables exist for sqlite or when migrations are not run in this environment.
        # Tests running against PostgreSQL should use Alembic migrations instead.
        try:
            Base.metadata.create_all(bind=sync_engine)
        except Exception:
            pass
    except Exception:
        # Best-effort; tests that run in-memory sqlite may not have sync_engine
        pass
    yield
    # no-op: creation finished

@pytest.fixture(scope="session", autouse=True)
def dispose_db_engines():
    """Session-scoped teardown that disposes DB engines used by tests.

    This fixture ensures synchronous and asynchronous engines are properly
    disposed at the end of the test session to avoid asyncpg warnings
    about terminating connections when the event loop is closed.

    It only performs disposal and does not change application behavior.
    """
    yield
    # Dispose sync engine if present
    try:
        sync = getattr(engine, "sync_engine", None)
        if sync is not None:
            try:
                sync.dispose()
            except Exception:
                # Let errors propagate — we don't mask disposal failures.
                raise
    finally:
        # Dispose async engine if possible (await event loop-safe disposal)
        try:
            # engine is an AsyncEngine; call dispose() which is async — run it
            # on the running loop if present, else create a temporary loop.
            import asyncio

            async def _do_dispose():
                await engine.dispose()

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # schedule disposal and wait for it synchronously
                fut = asyncio.run_coroutine_threadsafe(_do_dispose(), loop)
                fut.result()
            else:
                asyncio.run(_do_dispose())
        except Exception:
            # Let exceptions surface to pytest — do not swallow them
            raise
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


import asyncio


@pytest.fixture(autouse=True)
def cleanup_asyncio_tasks_and_engines():
    """Synchronous autouse fixture that performs asyncio cleanup after each test.

    Pytest will warn/error when a sync test depends on an async fixture. To
    maintain the same behavior while avoiding the deprecation, this fixture
    runs the async cleanup routine via ``asyncio.run`` so it's compatible with
    both sync and async tests.
    """
    yield

    async def _cleanup():
        # Allow scheduled tasks to run briefly
        try:
            await asyncio.sleep(0)
        except Exception:
            pass

        # Cancel any pending tasks except the current one
        current = asyncio.current_task()
        tasks = [t for t in asyncio.all_tasks() if t is not current]
        for t in tasks:
            if not t.done():
                t.cancel()

        # Wait for cancellations to finish
        if tasks:
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception:
                # swallow to avoid masking test failures
                pass

        # Dispose sync engine if present
        try:
            sync = getattr(engine, "sync_engine", None)
            if sync is not None:
                try:
                    sync.dispose()
                except Exception:
                    pass
        except Exception:
            pass

        # NOTE: Do NOT dispose the async engine here. Async engine disposal
        # is handled by the session-scoped `dispose_db_engines` fixture to
        # ensure disposal runs in a stable context and does not interfere
        # with pytest's event loop handling. Disposing the async engine
        # per-test can cause greenlet/async context errors (see SQLAlchemy
        # greenlet_spawn warnings) when tests run concurrently.

    try:
        asyncio.run(_cleanup())
    except RuntimeError:
        # If there's already a running event loop (e.g. in some test runners),
        # fall back to scheduling the coroutine on the running loop. This path
        # is uncommon in pytest's normal execution but keeps us robust.
        try:
            loop = asyncio.get_running_loop()
            fut = asyncio.run_coroutine_threadsafe(_cleanup(), loop)
            fut.result()
        except Exception:
            # Best-effort cleanup; do not mask test failures
            pass
