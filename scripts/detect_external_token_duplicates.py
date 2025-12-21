"""scripts/detect_external_token_duplicates.py

Simple admin utility to detect duplicate ExternalToken rows grouped by
(`tenant_id`, `provider`). Prints duplicates and suggests cleanup SQL that
keeps the most recently updated row for each duplicate group.

Usage:
  python scripts/detect_external_token_duplicates.py

Environment:
  Expects `DATABASE_URL` env var or the same configuration used by the app.
"""
from __future__ import annotations

import os
import asyncio
from app.db.session import engine
from sqlalchemy import text


async def main():
    query = """
    SELECT tenant_id, provider, count(*) as cnt
    FROM external_tokens
    GROUP BY tenant_id, provider
    HAVING count(*) > 1
    ORDER BY cnt DESC;
    """

    async with engine.connect() as conn:
        res = await conn.execute(text(query))
        rows = res.fetchall()

        if not rows:
            print("No duplicate external_tokens found.")
            return 0

        print("Duplicate groups (tenant_id, provider, count):")
        for r in rows:
            print(r)

        print("\nSuggested cleanup SQL (keep latest updated row for each group):\n")
        print("-- Run after careful review")
        print("WITH ranked AS (")
        print("  SELECT id, tenant_id, provider,")
        print("    ROW_NUMBER() OVER (PARTITION BY tenant_id, provider ORDER BY updated_at DESC, id DESC) AS rn")
        print("  FROM external_tokens")
        print(")")
        print("DELETE FROM external_tokens WHERE id IN (SELECT id FROM ranked WHERE rn > 1);")

    return 0


if __name__ == "__main__":
    asyncio.run(main())
