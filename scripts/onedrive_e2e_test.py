#!/usr/bin/env python3
"""
End-to-end OneDrive test using the project's OneDriveClient.

Performs: list_files, upload_file, download_file, delete_file for a test file.
Prints only OK/FAIL lines and exits with 0 on success.

WARNING: This performs real network calls and file writes. Use with care.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

from app.integrations.onedrive_client import OneDriveClient
from app.config import settings


TEST_FILENAME = "e2e_test_file.txt"


async def run_e2e() -> int:
    client = OneDriveClient()
    remote_path = f"{TEST_FILENAME}"
    local_tmp = Path(tempfile.gettempdir()) / TEST_FILENAME

    try:
        # 1) list files (should not raise)
        await client.list_files("")

        # 2) upload a small test file
        with open(local_tmp, "w") as fh:
            fh.write("e2e test\n")

        await client.upload_file(str(local_tmp), remote_path)

        # 3) download it back to a different tmp file
        download_path = str(local_tmp) + ".down"
        await client.download_file(remote_path, download_path)

        # 4) delete the file - implement via get_file_metadata + delete
        # OneDriveClient doesn't implement delete; perform a simple delete via item path
        # Use the internal API path construction and session to send DELETE
        session = await client._get_session()
        try:
            url = client._item_path_to_api(client._resolve_path(remote_path))
            async with session.delete(url) as resp:
                if resp.status >= 400:
                    print("FAIL: delete returned", resp.status)
                    return 2
        finally:
            if client._external_session is None:
                await session.close()

        # Cleanup local temp files
        try:
            os.remove(local_tmp)
        except Exception:
            pass
        try:
            os.remove(download_path)
        except Exception:
            pass

        print("OK: e2e succeeded")
        return 0

    except Exception as e:
        print("FAIL:", str(e))
        return 3


def main() -> None:
    code = asyncio.run(run_e2e())
    sys.exit(code)


if __name__ == "__main__":
    main()
