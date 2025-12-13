"""Create `integration_events` table if missing.

Usage:
    source .venv/bin/activate
    python3 scripts/create_integration_events.py
"""
import os
import sys
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set in environment (.env). Aborting.")
    sys.exit(1)

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import asyncio

SQL = """
CREATE TABLE IF NOT EXISTS integration_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  integration varchar NOT NULL,
  event_type varchar NOT NULL,
  level varchar NOT NULL,
  message text NOT NULL,
  context jsonb,
  created_at timestamp without time zone DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_integration_events_integration ON integration_events(integration);
CREATE INDEX IF NOT EXISTS idx_integration_events_event_type ON integration_events(event_type);
CREATE INDEX IF NOT EXISTS idx_integration_events_created_at ON integration_events(created_at);
"""


async def main():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        # Split into individual statements; asyncpg/prepared statements don't accept multiple commands
        stmts = [s.strip() for s in SQL.split(';') if s.strip()]
        for s in stmts:
            try:
                await conn.execute(text(s))
            except Exception as e:
                print(f"Failed statement: {s[:80]!r}..., error: {e}")
                raise
    await engine.dispose()
    print("integration_events table ensured.")


if __name__ == '__main__':
    asyncio.run(main())