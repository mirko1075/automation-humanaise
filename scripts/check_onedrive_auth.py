#!/usr/bin/env python3
"""
scripts/check_onedrive_auth.py

Simple script to verify OneDrive/Microsoft Graph app-only OAuth authentication.

Usage:
  python scripts/check_onedrive_auth.py

The script will read settings from `app.config.settings` (which loads `.env`).
It attempts to acquire an access token via `OAuthAuth` and prints a masked token on success.
"""
from __future__ import annotations

import asyncio
import sys
import time
from typing import Optional

from app.integrations.onedrive_client import OAuthAuth
from app.config import settings


async def _run_check() -> int:
    print("Checking OneDrive OAuth (app-only) authentication")
    mode = (settings.ONEDRIVE_AUTH_MODE or "app").lower()
    print(f"Configured ONEDRIVE_AUTH_MODE={mode}")

    if mode != "app":
        print("Note: ONEDRIVE_AUTH_MODE is not 'app' — this check will still attempt OAuth but your client may be configured for test mode.")

    oa = OAuthAuth()
    try:
        headers = await oa.get_auth_headers()
    except Exception as e:
        print("ERROR: token acquisition failed:", str(e))
        return 2

    token = headers.get("Authorization", "").split(" ", 1)[-1] if headers.get("Authorization") else None
    if not token:
        print("ERROR: No Authorization header returned")
        return 3

    # Mask token for output
    masked = token[:8] + "..." + token[-8:] if len(token) > 32 else token[:8] + "..."
    print("OK: acquired token (masked):", masked)
    return 0


def main() -> None:
    start = time.time()
    try:
        code = asyncio.run(_run_check())
    except KeyboardInterrupt:
        print("Interrupted")
        sys.exit(1)
    except Exception as e:
        print("Unexpected error:", e)
        sys.exit(4)
    elapsed = time.time() - start
    print(f"Elapsed: {elapsed:.2f}s")
    sys.exit(code)


if __name__ == "__main__":
    main()
