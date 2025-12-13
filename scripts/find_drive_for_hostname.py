#!/usr/bin/env python3
"""
Query Microsoft Graph for /sites/{hostname}/drive to obtain a drive id for SharePoint-backed personal sites.

Usage: PYTHONPATH=. python3 scripts/find_drive_for_hostname.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from app.integrations.onedrive_client import OneDriveClient
from app.config import settings


async def main() -> int:
    hostname = settings.ONEDRIVE_HOSTNAME
    if not hostname:
        print(json.dumps({"status": "fail", "error": "ONEDRIVE_HOSTNAME not set"}))
        return 2
    client = OneDriveClient()
    session = await client._get_session()
    try:
        url = f"{client.base_url}/sites/{hostname}/drive"
        async with session.get(url) as resp:
            if resp.status != 200:
                text = await resp.text()
                print(json.dumps({"status": "fail", "status_code": resp.status, "detail": text}))
                return 3
            j = await resp.json()
            drive_id = j.get("id")
            result = {"status": "ok", "drive_id": drive_id, "drive": j}
            print(json.dumps(result))
            return 0
    finally:
        if client._external_session is None:
            await session.close()


if __name__ == "__main__":
    code = asyncio.run(main())
    sys.exit(code)
