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

from typing import Protocol, Dict, Any, Optional, List, Union, Awaitable
import os
import aiohttp
import asyncio
from pathlib import Path
from app.config import settings
from app.monitoring.logger import log
from app.db.session import SessionLocal
from app.db.repositories.integration_event_repository import IntegrationEventRepository


class MicrosoftAuth(Protocol):
    """Auth interface providing headers for requests.

    Implementations may provide either a synchronous `get_auth_headers()` or
    an async `get_auth_headers()` coroutine. The client helper `_get_session`
    will handle both.
    """

    def get_auth_headers(self) -> Union[Dict[str, str], Awaitable[Dict[str, str]]]:
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
    """OAuth2 client credentials (app-only) auth provider for Microsoft Graph.

    - Uses the v2 token endpoint for the tenant
    - Requests scope `https://graph.microsoft.com/.default`
    - Caches token in memory and refreshes before expiration
    """

    TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None, tenant_id: Optional[str] = None, session: Optional[aiohttp.ClientSession] = None):
        self.client_id = client_id or settings.MS_CLIENT_ID
        self.client_secret = client_secret or settings.MS_CLIENT_SECRET
        self.tenant_id = tenant_id or settings.MS_TENANT_ID
        self._token: Optional[str] = None
        self._expires_at: Optional[float] = None
        self._lock = asyncio.Lock()
        self._session = session
        # Validate minimal config lazily; explicit validation happens at startup

    async def _fetch_token(self) -> None:
        if not (self.client_id and self.client_secret and self.tenant_id):
            log("ERROR", "OAuthAuth missing MS_CLIENT_ID/MS_CLIENT_SECRET/MS_TENANT_ID", module="onedrive_client")
            raise RuntimeError("OAuth credentials not configured for app-only auth")

        url = self.TOKEN_URL.format(tenant_id=self.tenant_id)
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }
        sess = self._session or aiohttp.ClientSession()
        created_local = self._session is None
        try:
            async with sess.post(url, data=data) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    log("ERROR", "OAuth token endpoint returned non-200", module="onedrive_client", status=resp.status)
                    raise RuntimeError(f"Token acquisition failed: {resp.status} {text}")
                j = await resp.json()
                access_token = j.get("access_token")
                expires_in = j.get("expires_in", 0)
                if not access_token:
                    log("ERROR", "OAuth token response missing access_token", module="onedrive_client")
                    raise RuntimeError("Token response missing access_token")
                self._token = access_token
                import time

                self._expires_at = time.time() + int(expires_in) - 60
                log("INFO", "OAuth token acquired", module="onedrive_client")
        finally:
            if created_local:
                await sess.close()

    async def _ensure_token(self) -> None:
        async with self._lock:
            import time

            if self._token and self._expires_at and time.time() < (self._expires_at - 30):
                # token still valid
                return
            # fetch new
            await self._fetch_token()

    async def get_auth_headers(self) -> Dict[str, str]:
        await self._ensure_token()
        return {"Authorization": f"Bearer {self._token}"}



class OneDriveClient:
    """Thin client for OneDrive operations using Microsoft Graph.

    All remote paths are resolved under `settings.ONEDRIVE_BASE_PATH` and
    must not escape that base folder.
    """

    def __init__(self, auth: MicrosoftAuth | None = None, session: aiohttp.ClientSession | None = None):
        # Choose default auth provider based on configuration
        if auth is not None:
            self.auth = auth
        else:
            mode = (settings.ONEDRIVE_AUTH_MODE or "app").lower()
            if mode == "test":
                self.auth = TestTokenAuth()
            else:
                # default to OAuth app-only in production
                self.auth = OAuthAuth()
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
        # Discovery is triggered by operations on demand (on 404) to avoid
        # racing background tasks and to keep discovery single-run and cached.
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
        # Persist a decision-level discovery_attempt event
        async with SessionLocal() as db:
            repo = IntegrationEventRepository(db)
            try:
                await repo.create(
                    integration="onedrive",
                    event_type="discovery_attempt",
                    level="INFO",
                    message="Starting OneDrive discovery sequence",
                    context={"drive_config": self.drive, "hostname": settings.ONEDRIVE_HOSTNAME},
                )
            except Exception:
                # Best-effort logging; do not break discovery on DB failure
                pass

        try:
            # 1) /me/drive
            try:
                # Log start of discovery attempt for /me/drive
                log("INFO", "OneDrive discovery: trying /me/drive", module="onedrive_client")
                async with session.get(f"{self.base_url}/me/drive") as resp:
                    status = resp.status
                    # Do not log token or response body
                    if status == 200:
                        data = await resp.json()
                        did = data.get("id")
                        if did:
                            self._drive_id_cached = did
                            self._drive_resolved = True
                            log("INFO", f"OneDrive discovery: using drive=drives/{did}", module="onedrive_client")
                            # Persist discovery_success
                            async with SessionLocal() as db:
                                repo = IntegrationEventRepository(db)
                                try:
                                    await repo.create(
                                        integration="onedrive",
                                        event_type="discovery_success",
                                        level="INFO",
                                        message="Resolved drive via /me/drive",
                                        context={"drive_id": did},
                                    )
                                except Exception:
                                    pass
                            return
                    elif status == 404:
                        log("WARNING", f"OneDrive discovery: /me/drive returned 404, trying /users/{{upn}}/drive", module="onedrive_client")
            except Exception:
                pass

            # 2) /users/{upn}/drive
            try:
                async with session.get(f"{self.base_url}/me") as me_resp:
                    me_status = me_resp.status
                    if me_status == 200:
                        me = await me_resp.json()
                        upn = me.get("userPrincipalName")
                        if upn:
                            async with session.get(f"{self.base_url}/users/{upn}/drive") as uresp:
                                u_status = uresp.status
                                if u_status == 200:
                                    data = await uresp.json()
                                    did = data.get("id")
                                    if did:
                                        self._drive_id_cached = did
                                        self._drive_resolved = True
                                        log("INFO", f"OneDrive discovery: using drive=drives/{did}", module="onedrive_client")
                                        async with SessionLocal() as db:
                                            repo = IntegrationEventRepository(db)
                                            try:
                                                await repo.create(
                                                    integration="onedrive",
                                                    event_type="discovery_success",
                                                    level="INFO",
                                                    message="Resolved drive via /users/{upn}/drive",
                                                    context={"drive_id": did, "user_upn": upn},
                                                )
                                            except Exception:
                                                pass
                                        return
                                elif u_status == 404:
                                    log("WARNING", f"OneDrive discovery: /users/{{upn}}/drive returned 404, trying site-based discovery (hostname={settings.ONEDRIVE_HOSTNAME})", module="onedrive_client")
                                    # Try users/{id}/drive as a secondary attempt using the user id from /me
                                    try:
                                        user_id = me.get("id")
                                        if user_id:
                                            async with session.get(f"{self.base_url}/users/{user_id}/drive") as uidresp:
                                                if uidresp.status == 200:
                                                    udata = await uidresp.json()
                                                    udid = udata.get("id")
                                                    if udid:
                                                        self._drive_id_cached = udid
                                                        self._drive_resolved = True
                                                        log("INFO", f"OneDrive discovery: using drive=drives/{udid} (via user id)", module="onedrive_client")
                                                        return
                                    except Exception:
                                        pass
            except Exception as e:
                log("WARNING", "OneDrive discovery exception", module="onedrive_client", error=str(e))

            # 3) site-based discovery using optional ONEDRIVE_HOSTNAME or derivation
            hostname = settings.ONEDRIVE_HOSTNAME
            if not hostname:
                hostname = None
            if hostname:
                try:
                    log("WARNING", f"OneDrive discovery: trying site-based discovery (hostname={hostname})", module="onedrive_client")
                    # Try GET /sites/{hostname}
                    async with session.get(f"{self.base_url}/sites/{hostname}") as sresp:
                        s_status = sresp.status
                        if s_status == 200:
                            site = await sresp.json()
                            site_id = site.get("id")
                            if site_id:
                                async with session.get(f"{self.base_url}/sites/{site_id}/drive") as sd:
                                    if sd.status == 200:
                                        ddata = await sd.json()
                                        did = ddata.get("id")
                                        if did:
                                            self._drive_id_cached = did
                                            self._drive_resolved = True
                                            log("INFO", f"OneDrive discovery: resolved drive via site {hostname} -> drive_id={did}", module="onedrive_client")
                                            async with SessionLocal() as db:
                                                repo = IntegrationEventRepository(db)
                                                try:
                                                    await repo.create(
                                                        integration="onedrive",
                                                        event_type="discovery_success",
                                                        level="INFO",
                                                        message="Resolved drive via site discovery",
                                                        context={"hostname": hostname, "drive_id": did},
                                                    )
                                                except Exception:
                                                    pass
                                            log("INFO", f"OneDrive discovery: using drive=drives/{did}", module="onedrive_client")
                                            return

                    # Personal site attempt: derive user segment from /me userPrincipalName
                    async with session.get(f"{self.base_url}/me") as me_resp2:
                        if me_resp2.status == 200:
                            me2 = await me_resp2.json()
                            upn2 = me2.get("userPrincipalName")
                            if upn2:
                                user_segment = upn2.lower().replace("@", "_").replace(".", "_")
                                # Log attempt to use personal site path
                                log("INFO", f"OneDrive discovery: trying personal site /personal/{user_segment}", module="onedrive_client")
                                personal_path = f"/personal/{user_segment}"
                                # Attempt GET /sites/{hostname}:/personal/{user_segment}:/drive
                                async with session.get(f"{self.base_url}/sites/{hostname}:{personal_path}:/drive") as psresp:
                                    ps_status = psresp.status
                                    if ps_status == 200:
                                        pdata = await psresp.json()
                                        pdid = pdata.get("id")
                                        if pdid:
                                            self._drive_id_cached = pdid
                                            self._drive_resolved = True
                                            log("INFO", f"OneDrive discovery: resolved drive via personal site -> drive_id={pdid}", module="onedrive_client")
                                            async with SessionLocal() as db:
                                                repo = IntegrationEventRepository(db)
                                                try:
                                                    await repo.create(
                                                        integration="onedrive",
                                                        event_type="discovery_success",
                                                        level="INFO",
                                                        message="Resolved drive via personal site",
                                                        context={"hostname": hostname, "user_segment": user_segment, "drive_id": pdid},
                                                    )
                                                except Exception:
                                                    pass
                                            log("INFO", f"OneDrive discovery: using drive=drives/{pdid}", module="onedrive_client")
                                            return
                                    else:
                                        log("WARNING", f"OneDrive discovery: personal site lookup failed (status={ps_status})", module="onedrive_client")

                                # If direct personal site path failed, try searching sites by user segment
                                log("INFO", f"OneDrive discovery: searching sites for personal segment '{user_segment}'", module="onedrive_client")
                                async with session.get(f"{self.base_url}/sites?search={user_segment}") as ssearch:
                                    if ssearch.status == 200:
                                        sdata = await ssearch.json()
                                        for site_item in sdata.get("value", []):
                                            weburl = site_item.get("webUrl", "") or ""
                                            if "/personal/" in weburl:
                                                site_id_found = site_item.get("id")
                                                if site_id_found:
                                                    async with session.get(f"{self.base_url}/sites/{site_id_found}/drive") as psd:
                                                        if psd.status == 200:
                                                            pd = await psd.json()
                                                            pdid2 = pd.get("id")
                                                            if pdid2:
                                                                self._drive_id_cached = pdid2
                                                                self._drive_resolved = True
                                                                log("INFO", f"OneDrive discovery: resolved drive via site search -> drive_id={pdid2}", module="onedrive_client")
                                                                async with SessionLocal() as db:
                                                                    repo = IntegrationEventRepository(db)
                                                                    try:
                                                                        await repo.create(
                                                                            integration="onedrive",
                                                                            event_type="discovery_success",
                                                                            level="INFO",
                                                                            message="Resolved drive via site search",
                                                                            context={"site_id": site_id_found, "drive_id": pdid2},
                                                                        )
                                                                    except Exception:
                                                                        pass
                                                                log("INFO", f"OneDrive discovery: using drive=drives/{pdid2}", module="onedrive_client")
                                                                return
                                    else:
                                        log("WARNING", f"OneDrive discovery: site search returned status={ssearch.status}", module="onedrive_client")

                    # Additional fallback: enumerate /drives and attempt to match by owner or webUrl
                    log("INFO", "OneDrive discovery: trying /drives to locate personal drive", module="onedrive_client")
                    async with session.get(f"{self.base_url}/drives") as drives_resp:
                        if drives_resp.status == 200:
                            drives_json = await drives_resp.json()
                            for d in drives_json.get("value", []):
                                # Try matching by owner.user.email / owner.user.id
                                owner = d.get("owner") or {}
                                user_info = owner.get("user") or {}
                                weburl = d.get("webUrl", "") or ""
                                if upn2 and (user_info.get("email") == upn2 or user_info.get("id") == me2.get("id") or f"/personal/{user_segment}" in weburl):
                                    did_found = d.get("id")
                                    if did_found:
                                        self._drive_id_cached = did_found
                                        self._drive_resolved = True
                                        log("INFO", f"OneDrive discovery: resolved drive via drives listing -> drive_id={did_found}", module="onedrive_client")
                                        async with SessionLocal() as db:
                                            repo = IntegrationEventRepository(db)
                                            try:
                                                await repo.create(
                                                    integration="onedrive",
                                                    event_type="discovery_success",
                                                    level="INFO",
                                                    message="Resolved drive via drives listing",
                                                    context={"drive_id": did_found},
                                                )
                                            except Exception:
                                                pass
                                        log("INFO", f"OneDrive discovery: using drive=drives/{did_found}", module="onedrive_client")
                                        return
                        else:
                            log("WARNING", f"OneDrive discovery: /drives returned status={drives_resp.status}", module="onedrive_client")
                except Exception as e:
                    log("WARNING", "OneDrive discovery exception", module="onedrive_client", hostname=hostname, error=str(e))
        finally:
            if self._external_session is None:
                await session.close()
        # mark as resolved to avoid repeated attempts
        self._drive_resolved = True
        # If we reach here without a cached drive id, log fallback once and persist a decision-level event
        if not self._drive_id_cached:
            # final fallback to configured MS_DRIVE_ID
            log("WARNING", f"OneDrive discovery failed; falling back to configured MS_DRIVE_ID={settings.MS_DRIVE_ID}", module="onedrive_client")
            log("INFO", f"OneDrive discovery: using drive={settings.MS_DRIVE_ID}", module="onedrive_client")
            try:
                async with SessionLocal() as db:
                    repo = IntegrationEventRepository(db)
                    await repo.create(
                        integration="onedrive",
                        event_type="discovery_failed",
                        level="WARN",
                        message="Discovery failed; falling back to configured drive",
                        context={"drive_config": self.drive, "hostname": settings.ONEDRIVE_HOSTNAME},
                    )
            except Exception:
                pass

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._external_session is not None:
            return self._external_session
        # Support auth providers that return headers either synchronously or
        # asynchronously.
        headers = self.auth.get_auth_headers()
        if asyncio.iscoroutine(headers):
            headers = await headers
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
                    # If we get 404 and discovery hasn't run, trigger discovery and retry once.
                    if resp.status == 404 and not self._drive_resolved:
                        # close session from this call if we created it
                        if self._external_session is None:
                            await session.close()
                        # run discovery (this logs the process)
                        await self._discover_drive()
                        # retry the request with possibly updated drive id
                        session = await self._get_session()
                        async with session.get(self._item_path_to_api(path) + ":/children") as resp2:
                            text2 = await resp2.text()
                            if resp2.status >= 400:
                                log("ERROR", f"List files failed: {resp2.status} {text2}", module="onedrive_client")
                                raise RuntimeError(f"List files failed: {resp2.status} {text2}")
                            data = await resp2.json()
                            items = data.get("value", [])
                            log("INFO", f"Listed {len(items)} items", module="onedrive_client")
                            return items
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
                    if resp.status == 404 and not self._drive_resolved:
                        if self._external_session is None:
                            await session.close()
                        await self._discover_drive()
                        session = await self._get_session()
                        async with session.get(self._item_path_to_api(path)) as resp2:
                            text2 = await resp2.text()
                            if resp2.status >= 400:
                                log("ERROR", f"Get metadata failed: {resp2.status} {text2}", module="onedrive_client")
                                raise RuntimeError(f"Get metadata failed: {resp2.status} {text2}")
                            data = await resp2.json()
                            log("INFO", f"Metadata fetched", module="onedrive_client")
                            return data
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
                    if resp.status == 404 and not self._drive_resolved:
                        if self._external_session is None:
                            await session.close()
                        await self._discover_drive()
                        session = await self._get_session()
                        async with session.get(self._item_path_to_api(path) + ":/content") as resp2:
                            if resp2.status >= 400:
                                text2 = await resp2.text()
                                log("ERROR", f"Download failed: {resp2.status} {text2}", module="onedrive_client")
                                raise RuntimeError(f"Download failed: {resp2.status} {text2}")
                            local_dir = Path(local_path).parent
                            local_dir.mkdir(parents=True, exist_ok=True)
                            with open(local_path, "wb") as fh:
                                async for chunk in resp2.content.iter_chunked(1024 * 64):
                                    fh.write(chunk)
                            log("INFO", f"Download completed: {local_path}", module="onedrive_client")
                            return
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
                        if resp.status == 404 and not self._drive_resolved:
                            if self._external_session is None:
                                await session.close()
                            await self._discover_drive()
                            session = await self._get_session()
                            with open(local_path, "rb") as fh2:
                                async with session.put(self._item_path_to_api(path) + ":/content", data=fh2) as resp2:
                                    text2 = await resp2.text()
                                    if resp2.status >= 400:
                                        log("ERROR", f"Upload failed: {resp2.status} {text2}", module="onedrive_client")
                                        raise RuntimeError(f"Upload failed: {resp2.status} {text2}")
                                    data2 = await resp2.json()
                                    log("INFO", f"Upload completed: {path}", module="onedrive_client")
                                    return data2
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
