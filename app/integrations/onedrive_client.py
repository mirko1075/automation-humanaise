"""app/integrations/onedrive_client.py
OneDrive client wrapper for Microsoft Graph operations.

Responsibilities:
- Provide an auth interface used by the client (get_auth_headers)
- TestTokenAuth reads `MS_ACCESS_TOKEN` from env for manual testing
- OneDriveClient exposes: upload_file, download_file, list_files, get_file_metadata

Notes:
- OAuth flows are intentionally NOT implemented here. See `OAuthAuth` placeholder.
"""
from __future__ import annotations

from typing import Protocol, Dict, Any, Optional, List
import os
import aiohttp
import asyncio
from pathlib import Path
from app.config import settings
from app.monitoring.logger import log


class MicrosoftAuth(Protocol):
    """Auth interface providing headers for requests."""

    def get_auth_headers(self) -> Dict[str, str]:
        ...


class TestTokenAuth:
    """Simple auth provider that reads `MS_ACCESS_TOKEN` from env/settings.

    This is intended for manual testing with a personal OneDrive access token.
    Do NOT use in production. For production, implement OAuthAuth (placeholder below).
    """

    def __init__(self, token: Optional[str] = None):
        self.token = token or settings.MS_ACCESS_TOKEN

    def get_auth_headers(self) -> Dict[str, str]:
        if not self.token:
            raise RuntimeError("MS_ACCESS_TOKEN not provided for TestTokenAuth")
        return {"Authorization": f"Bearer {self.token}"}


class OAuthAuth:
    """TODO: Implement OAuth client-credentials or other flows later.

    Placeholder class so the rest of the code depends on the auth interface only.
    """

    def __init__(self):
        raise NotImplementedError("OAuthAuth must be implemented using client credentials flow")


class OneDriveClient:
    """Thin client for OneDrive operations using Microsoft Graph.

    All remote paths are resolved under `settings.ONEDRIVE_BASE_PATH` and
    must not escape that base folder.
    """

    def __init__(self, auth: MicrosoftAuth | None = None, session: aiohttp.ClientSession | None = None):
        self.auth = auth or TestTokenAuth()
        self.base_url = settings.MS_GRAPH_BASE_URL.rstrip("/")
        self.drive = settings.MS_DRIVE_ID or "me/drive"
        self.base_path = settings.ONEDRIVE_BASE_PATH.rstrip("/") or "/TEST"
        self._external_session = session
        self._drive_resolved = False
        self._drive_id_cached: Optional[str] = None

    def _resolve_path(self, remote_path: str) -> str:
        # Ensure remote_path is relative and stays within base_path
        rp = remote_path.lstrip("/")
        full = f"{self.base_path}/{rp}".replace("//", "/")
        if not full.startswith(self.base_path):
            raise ValueError("remote_path must be under ONEDRIVE_BASE_PATH")
        return full

    def _item_path_to_api(self, path: str) -> str:
        # Microsoft Graph path for drive items by path: /drives/{drive}/root:/<path>
        # If settings.MS_DRIVE_ID is of form 'me/drive', we handle it.
        # We resolve drive id lazily to support personal/business/SharePoint-backed drives.
        drive_part = self.drive
        if not self._drive_resolved:
            # attempt discovery; non-blocking on external session creation
            # discovery modifies self._drive_id_cached or keeps self.drive
            # We'll run discovery synchronously via asyncio.run if necessary
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                # We're in an event loop (normal case); schedule discovery task
                # but do not block here — instead assume the configured MS_DRIVE_ID works
                # If discovery completes later it will update the cached id.
                asyncio.create_task(self._discover_drive())
            else:
                # Not in an event loop (CLI), run discovery now
                asyncio.run(self._discover_drive())
        if self._drive_id_cached:
            return f"{self.base_url}/drives/{self._drive_id_cached}/root:{path}"
        if drive_part == "me/drive":
            return f"{self.base_url}/me/drive/root:{path}"
        # allow passing drive id or drives/{id}
        if drive_part.startswith("drives/"):
            return f"{self.base_url}/{drive_part}/root:{path}"
        return f"{self.base_url}/drives/{drive_part}/root:{path}"

    async def _discover_drive(self) -> None:
        """Discover a usable drive id for the current authenticated user.

        Tries (in order): /me/drive, /users/{upn}/drive, site-based via ONEDRIVE_HOSTNAME.
        Caches resulting drive id in `self._drive_id_cached` for future requests.
        """
        if self._drive_resolved:
            return
        session = await self._get_session()
        try:
            # 1) /me/drive
            try:
                async with session.get(f"{self.base_url}/me/drive") as resp:
                    status = resp.status
                    text = await resp.text()
                    log("DEBUG", "drive_discovery_attempt", module="onedrive_client", attempt="me_drive", status=status)
                    if status == 200:
                        data = await resp.json()
                        did = data.get("id")
                        if did:
                            self._drive_id_cached = did
                            self._drive_resolved = True
                            log("INFO", "drive_discovery", module="onedrive_client", method="me_drive", drive_id=did)
                            return
            except Exception:
                pass

            # 2) /users/{upn}/drive
            try:
                async with session.get(f"{self.base_url}/me") as me_resp:
                    me_status = me_resp.status
                    me_text = await me_resp.text()
                    log("DEBUG", "drive_discovery_attempt", module="onedrive_client", attempt="me_profile", status=me_status)
                    if me_status == 200:
                        me = await me_resp.json()
                        upn = me.get("userPrincipalName")
                        if upn:
                            async with session.get(f"{self.base_url}/users/{upn}/drive") as uresp:
                                u_status = uresp.status
                                u_text = await uresp.text()
                                log("DEBUG", "drive_discovery_attempt", module="onedrive_client", attempt="users_upn_drive", upn=upn, status=u_status)
                                if u_status == 200:
                                    data = await uresp.json()
                                    did = data.get("id")
                                    if did:
                                        self._drive_id_cached = did
                                        self._drive_resolved = True
                                        log("INFO", "drive_discovery", module="onedrive_client", method="users_upn_drive", upn=upn, drive_id=did)
                                        return
            except Exception as e:
                log("WARNING", "drive_discovery_exception", module="onedrive_client", error=str(e))

            # 3) site-based discovery using optional ONEDRIVE_HOSTNAME or derivation
            hostname = settings.ONEDRIVE_HOSTNAME
            if not hostname:
                # attempt to parse hostname from MS_DRIVE_ID if it contains a hostname
                # e.g., sites/{hostname} or hostname-like
                # Otherwise skip site-based discovery
                hostname = None
            if hostname:
                try:
                    async with session.get(f"{self.base_url}/sites/{hostname}") as sresp:
                        s_status = sresp.status
                        s_text = await sresp.text()
                        log("DEBUG", "drive_discovery_attempt", module="onedrive_client", attempt="site_lookup", hostname=hostname, status=s_status)
                        if s_status == 200:
                            site = await sresp.json()
                            site_id = site.get("id")
                            if site_id:
                                async with session.get(f"{self.base_url}/sites/{site_id}/drive") as sd:
                                    sd_status = sd.status
                                    sd_text = await sd.text()
                                    log("DEBUG", "drive_discovery_attempt", module="onedrive_client", attempt="site_drive", site_id=site_id, status=sd_status)
                                    if sd_status == 200:
                                        ddata = await sd.json()
                                        did = ddata.get("id")
                                        if did:
                                            self._drive_id_cached = did
                                            self._drive_resolved = True
                                            log("INFO", "drive_discovery", module="onedrive_client", method="site_drive", site_id=site_id, drive_id=did)
                                            return
                except Exception as e:
                    log("WARNING", "drive_discovery_exception", module="onedrive_client", hostname=hostname, error=str(e))
        finally:
            if self._external_session is None:
                await session.close()
        # mark as resolved to avoid repeated attempts
        self._drive_resolved = True

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._external_session is not None:
            return self._external_session
        headers = self.auth.get_auth_headers()
        return aiohttp.ClientSession(headers={**headers, "Accept": "application/json"})

    async def list_files(self, remote_path: str) -> List[Dict[str, Any]]:
        """List children of a folder under ONEDRIVE_BASE_PATH/remote_path."""
        path = self._resolve_path(remote_path)
        url = self._item_path_to_api(path) + ":/children"
        log("INFO", f"Listing files in OneDrive: {path}", module="onedrive_client")
        session = await self._get_session()
        try:
            async with session.get(url) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    log("ERROR", f"List files failed: {resp.status} {text}", module="onedrive_client")
                    raise RuntimeError(f"List files failed: {resp.status} {text}")
                data = await resp.json()
                items = data.get("value", [])
                log("INFO", f"Listed {len(items)} items", module="onedrive_client")
                return items
        finally:
            if self._external_session is None:
                await session.close()

    async def get_file_metadata(self, remote_path: str) -> Dict[str, Any]:
        path = self._resolve_path(remote_path)
        url = self._item_path_to_api(path)
        log("INFO", f"Fetching metadata for OneDrive file: {path}", module="onedrive_client")
        session = await self._get_session()
        try:
            async with session.get(url) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    log("ERROR", f"Get metadata failed: {resp.status} {text}", module="onedrive_client")
                    raise RuntimeError(f"Get metadata failed: {resp.status} {text}")
                data = await resp.json()
                log("INFO", f"Metadata fetched", module="onedrive_client")
                return data
        finally:
            if self._external_session is None:
                await session.close()

    async def download_file(self, remote_path: str, local_path: str) -> None:
        path = self._resolve_path(remote_path)
        url = self._item_path_to_api(path) + ":/content"
        log("INFO", f"Downloading OneDrive file: {path} -> {local_path}", module="onedrive_client")
        session = await self._get_session()
        try:
            async with session.get(url) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    log("ERROR", f"Download failed: {resp.status} {text}", module="onedrive_client")
                    raise RuntimeError(f"Download failed: {resp.status} {text}")
                # Stream to file
                local_dir = Path(local_path).parent
                local_dir.mkdir(parents=True, exist_ok=True)
                with open(local_path, "wb") as fh:
                    async for chunk in resp.content.iter_chunked(1024 * 64):
                        fh.write(chunk)
                log("INFO", f"Download completed: {local_path}", module="onedrive_client")
        finally:
            if self._external_session is None:
                await session.close()

    async def upload_file(self, local_path: str, remote_path: str) -> Dict[str, Any]:
        path = self._resolve_path(remote_path)
        url = self._item_path_to_api(path) + ":/content"
        log("INFO", f"Uploading file to OneDrive: {path} from {local_path}", module="onedrive_client")
        if not Path(local_path).exists():
            log("ERROR", f"Local file not found: {local_path}", module="onedrive_client")
            raise FileNotFoundError(local_path)
        session = await self._get_session()
        try:
            with open(local_path, "rb") as fh:
                async with session.put(url, data=fh) as resp:
                    text = await resp.text()
                    if resp.status >= 400:
                        log("ERROR", f"Upload failed: {resp.status} {text}", module="onedrive_client")
                        raise RuntimeError(f"Upload failed: {resp.status} {text}")
                    data = await resp.json()
                    log("INFO", f"Upload completed: {path}", module="onedrive_client")
                    return data
        finally:
            if self._external_session is None:
                await session.close()


async def main_cli():
    import argparse

    parser = argparse.ArgumentParser(description="OneDrive client CLI (testing only)")
    parser.add_argument("action", choices=["upload", "download", "list", "meta"])
    parser.add_argument("remote_path")
    parser.add_argument("local_path", nargs="?", default=None)
    args = parser.parse_args()
    client = OneDriveClient()
    if args.action == "list":
        items = await client.list_files(args.remote_path)
        print(items)
    elif args.action == "meta":
        meta = await client.get_file_metadata(args.remote_path)
        print(meta)
    elif args.action == "download":
        if not args.local_path:
            raise SystemExit("download requires local_path")
        await client.download_file(args.remote_path, args.local_path)
    elif args.action == "upload":
        if not args.local_path:
            raise SystemExit("upload requires local_path")
        res = await client.upload_file(args.local_path, args.remote_path)
        print(res)


if __name__ == "__main__":
    asyncio.run(main_cli())
