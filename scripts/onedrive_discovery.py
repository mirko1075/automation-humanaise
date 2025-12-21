#!/usr/bin/env python3
"""OneDrive drive discovery helper.

Attempts discovery using the project's OneDriveClient and prints structured JSON
with the discovered drive_id, driveType and owner when found.
"""
from __future__ import annotations

import asyncio
import json
import sys
from typing import Optional

from app.integrations.onedrive_client import OneDriveClient
from app.config import settings


async def fetch_drive_metadata(client: OneDriveClient, drive_id: str) -> dict:
    """Attempt to fetch drive metadata (driveType, owner) for the given drive_id.

    Tries multiple endpoints depending on the form of drive_id.
    """
    session = await client._get_session()
    try:
        candidates = []
        # If drive_id looks like a GUID or id, try /drives/{drive_id}
        if drive_id and not drive_id.startswith("me/") and not drive_id.startswith("drives/"):
            candidates.append(f"{client.base_url}/drives/{drive_id}")
        # try drives/{drive_id}
        candidates.append(f"{client.base_url}/drives/{drive_id}")
        # try /me/drive
        candidates.append(f"{client.base_url}/me/drive")

        for url in candidates:
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        j = await resp.json()
                        return j
            except Exception:
                continue
    finally:
        if client._external_session is None:
            await session.close()
    return {}


async def main() -> int:
    client = OneDriveClient()
    try:
        # Force discovery logic to run
        await client._discover_drive()
        drive_id: Optional[str] = getattr(client, "_drive_id_cached", None) or settings.MS_DRIVE_ID
        if not drive_id:
            print(json.dumps({"status": "fail", "error": "drive discovery failed"}))
            return 2

        meta = await fetch_drive_metadata(client, drive_id)
        # Extract useful fields, avoid logging secrets
        drive_type = meta.get("driveType") if isinstance(meta, dict) else None
        owner = None
        if isinstance(meta, dict):
            owner = meta.get("owner") or meta.get("createdBy") or None

        result = {
            "status": "ok",
            "drive_id": drive_id,
            "drive_type": drive_type,
            "owner": owner,
        }
        print(json.dumps(result))
        return 0
    except Exception as e:
        print(json.dumps({"status": "fail", "error": str(e)}))
        return 3


if __name__ == "__main__":
    code = asyncio.run(main())
    sys.exit(code)
