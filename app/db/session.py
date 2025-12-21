# app/db/session.py
"""
Database session utilities and readiness check.
"""
import os
from typing import Optional

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


def _get_database_url() -> Optional[str]:
    """Fetch DATABASE_URL from environment or .env-loaded settings."""
    # Prefer explicit environment variable but fall back to the application's
    # configured settings (Pydantic) when present. Importing `settings` at
    # module import time may introduce circular imports for some test helpers,
    # so perform the import lazily.
    dsn = os.getenv("DATABASE_URL")
    if dsn:
        return dsn
    try:
        from app.config import settings

        return getattr(settings, "DATABASE_URL", None)
    except Exception:
        return None


async def check_db_ready() -> bool:
    """Return True if the database responds to a simple SELECT 1, else False."""
    dsn = _get_database_url()
    if not dsn:
        return False

    try:
        engine = create_async_engine(dsn, pool_pre_ping=True)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return True
    except Exception:
        return False
# app/db/session.py
"""
Database session and base class setup (SQLAlchemy 2.0 style).
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings

DATABASE_URL = settings.DATABASE_URL

# If tests set an in-memory SQLite URL, replace it with a file-backed URL
# so multiple connections share the same schema during pytest runs.
if DATABASE_URL and ":memory:" in DATABASE_URL:
    file_db = "sqlite+aiosqlite:///./.test_sqlite.db"
    DATABASE_URL = file_db

engine = create_async_engine(DATABASE_URL, future=True, echo=False)
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


def ensure_tables_async():
    """Return an async callable that creates tables when awaited.

    Tests can import this helper and run it from an async fixture to create
    schema without triggering event loop management at import time.
    """

    async def _create_tables():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    return _create_tables


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an `AsyncSession` instance.

    Usage in endpoints:
        db: AsyncSession = Depends(get_async_session)

    Returns:
        AsyncGenerator yielding a database session that is closed after use.
    """
    async with SessionLocal() as session:
        yield session
