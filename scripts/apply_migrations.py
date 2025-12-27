"""Simple migration runner to apply SQL files in `migrations/` in alphabetical order.
import os
import sys
import glob
import asyncio
import logging

if not logging.getLogger().hasHandlers():
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
logger = logging.getLogger(__name__)

# ...existing code...

from sqlalchemy import text
    if not DATABASE_URL:
        logger.error("DATABASE_URL not set in environment (.env). Aborting.")
        sys.exit(1)
    # ...existing code...
    if not sql_files:
        logger.info("No migration files found in migrations/")
        return
    logger.info(f"Applying {len(sql_files)} migrations to {DATABASE_URL}")
    # ...existing code...
    for sql_file in sql_files:
        logger.info(f"Applying {sql_file.name}")
        # ...existing code...
        try:
            # ...existing code...
            logger.info(f"Applied {sql_file.name}")
        except Exception as e:
            logger.error(f"Failed applying {sql_file.name}: {e}")
    logger.info("Migrations applied.")
from sqlalchemy.ext.asyncio import create_async_engine


async def apply_migrations():
    migrations_dir = Path(__file__).resolve().parent.parent / "migrations"
    sql_files = sorted(migrations_dir.glob("*.sql"))
    if not sql_files:
        print("No migration files found in migrations/")
        return 0

    print(f"Applying {len(sql_files)} migrations to {DATABASE_URL}")
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        for sql_file in sql_files:
            print(f"Applying {sql_file.name}")
            raw = sql_file.read_text()
            # Strip leading triple-quoted preamble if present
            stripped = raw.lstrip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                delim = stripped[:3]
                end_idx = stripped.find(delim, 3)
                if end_idx != -1:
                    stripped = stripped[end_idx+3:]

            # Remove leading non-SQL lines until we find a SQL comment or statement
            lines = stripped.splitlines()
            start = 0
            for i, ln in enumerate(lines):
                if not ln.strip():
                    continue
                up = ln.strip().upper()
                if up.startswith('--') or up.startswith('/*') or up.split()[0].upper() in ('CREATE', 'ALTER', 'INSERT', 'UPDATE', 'DELETE', 'WITH', 'DROP'):
                    start = i
                    break
            sql = "\n".join(lines[start:])

            # Split into individual statements by semicolon. This is simple but sufficient
            # for the migration SQL files we include (no semicolons inside string literals).
            statements = [s.strip() for s in sql.split(';') if s.strip()]
            try:
                for stmt in statements:
                    # Skip pure comment statements
                    if stmt.strip().startswith('--'):
                        continue
                    await conn.execute(text(stmt))
                print(f"Applied {sql_file.name}")
            except Exception as e:
                print(f"Failed applying {sql_file.name}: {e}")
                return 2
    await engine.dispose()
    print("Migrations applied.")
    return 0


if __name__ == "__main__":
    code = asyncio.run(apply_migrations())
    sys.exit(code)
