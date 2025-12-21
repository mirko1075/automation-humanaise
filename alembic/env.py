"""
Alembic env.py for async SQLAlchemy usage.

This file ensures Alembic reads `DATABASE_URL` from the environment when
present (Render provides it at deploy time). It intentionally does not
hardcode credentials or DB names.

It uses the async migration pattern from Alembic docs and calls the
offline/online migration routines as appropriate.
"""
from __future__ import annotations

import os
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import create_engine
from sqlalchemy import engine_from_config

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import models' MetaData here for 'autogenerate' support
try:
    # app.db.models may assemble Base metadata via SQLAlchemy declarative_base
    from app.db.session import Base
    target_metadata = Base.metadata
except Exception:
    target_metadata = None


def get_database_url() -> str:
    """Return DB URL, prefer `DATABASE_URL` environment variable.

    Render and other platforms inject `DATABASE_URL` so we must prefer it.
    """
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url
    # Fallback: use alembic.ini sqlalchemy.url if present
    cfg = config.get_main_option("sqlalchemy.url")
    if not cfg:
        raise RuntimeError("DATABASE_URL not set in environment and sqlalchemy.url missing in alembic.ini")
    return cfg


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable as well.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (with an Engine).

    Uses an async engine for the connection and runs migrations synchronously
    using a sync connection from the engine.
    """

    # Read URL and create a sync engine for Alembic work
    url = get_database_url()
    # If the application uses an async dialect URL (e.g. postgresql+asyncpg://)
    # convert it to a sync dialect for Alembic's synchronous engine.
    # This keeps the application's DATABASE_URL usable (async) while allowing
    # Alembic to run using a sync driver.
    sync_url = url
    if sync_url.startswith("postgresql+asyncpg://"):
        # remove the +asyncpg part so SQLAlchemy uses a sync driver (psycopg)
        sync_url = sync_url.replace("+asyncpg", "")
    connectable = create_engine(sync_url)

    with connectable.connect() as connection:
        do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
