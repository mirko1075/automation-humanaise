"""Small one-off script to test OneDrive access using TestTokenAuth.

Usage (from repo root):
  set -o allexport; source .env; set +o allexport
  PYTHONPATH=. .venv/bin/python scripts/onedrive_test.py

This script will NOT print your access token. It lists the target folder,
uploads a small text file under `preventivi/`, downloads it back, and
verifies the contents.
"""
from __future__ import annotations

import asyncio
import tempfile
import os
from datetime import datetime
from pathlib import Path

from app.integrations.onedrive_client import OneDriveClient, TestTokenAuth
from app.config import settings


async def main() -> None:
    print("OneDrive test starting...")
    # Do not print secrets
    auth = TestTokenAuth()
    client = OneDriveClient(auth=auth)

    base = settings.ONEDRIVE_BASE_PATH
    print(f"Using ONEDRIVE_BASE_PATH: {base}")

    try:
        items = await client.list_files("")
        print(f"Listed {len(items)} items in {base}")
    except Exception as e:
        print("List failed:", str(e))
        return

    # Prepare a small temp file to upload
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    remote = f"preventivi/test_upload_{ts}.txt"
    with tempfile.NamedTemporaryFile(delete=False, mode="wb") as fh:
        content = f"onedrive test {ts}\n".encode("utf-8")
        fh.write(content)
        local_path = fh.name

    print(f"Uploading test file to: {remote}")
    try:
        res = await client.upload_file(local_path, remote)
        print("Upload succeeded")
    except Exception as e:
        print("Upload failed:", str(e))
        Path(local_path).unlink(missing_ok=True)
        return

    # Download back
    dl_path = local_path + ".downloaded"
    try:
        await client.download_file(remote, dl_path)
        print("Download succeeded")
    except Exception as e:
        print("Download failed:", str(e))
        Path(local_path).unlink(missing_ok=True)
        return

    # Verify contents
    try:
        read = Path(dl_path).read_bytes()
        if read == content:
            print("Round-trip content verified — OK")
        else:
            print("Content mismatch: expected", len(content), "bytes, got", len(read), "bytes")
    finally:
        # cleanup local temporary files
        Path(local_path).unlink(missing_ok=True)
        Path(dl_path).unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(main())
