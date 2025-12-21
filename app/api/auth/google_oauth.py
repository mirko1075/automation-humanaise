"""
app/api/auth/google_oauth.py

Google OAuth helper endpoints:
 - GET /auth/google/login -> redirects to Google's OAuth consent screen
 - GET /auth/google/callback -> exchanges code for tokens and stores them

This module implements the minimal public-facing endpoints required to
obtain Gmail API access/refresh tokens for a tenant and persist them
in `ExternalTokenRepository`.
"""
from typing import Any, Dict, Optional
from urllib.parse import urlencode, urljoin
import base64
import json
from datetime import datetime, timezone, timedelta

import httpx
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse, JSONResponse

import os
from app.config import settings
from app.monitoring.logger import log
from app.db.session import get_async_session
from app.db.repositories.external_token_repository import ExternalTokenRepository

router = APIRouter(prefix="/auth", tags=["auth"])

# Public alias router (no prefix) to expose `/google/login` as requested
public_router = APIRouter(tags=["auth-public"]) 


def _encode_state(state: Dict[str, Any]) -> str:
    """Encode state dict into a URL-safe string."""
    s = json.dumps(state)
    return base64.urlsafe_b64encode(s.encode()).decode()


def _decode_state(state_str: str) -> Dict[str, Any]:
    try:
        raw = base64.urlsafe_b64decode(state_str.encode()).decode()
        return json.loads(raw)
    except Exception:
        return {}


@router.get("/google/login")
async def google_login(request: Request) -> RedirectResponse:
    """Redirect user to Google OAuth consent screen.

    Query parameters:
      - tenant_id (optional): if provided, it will be encoded into `state`.
    """
    tenant_id = request.query_params.get("tenant_id")
    client_id = os.getenv("GOOGLE_CLIENT_ID") or settings.GOOGLE_CLIENT_ID
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI") or settings.GOOGLE_REDIRECT_URI

    if not client_id or not redirect_uri:
        log("ERROR", "Google OAuth login attempted but config missing", module="google_oauth")
        raise HTTPException(status_code=500, detail="Google OAuth not configured")

    state = {"tenant_id": tenant_id} if tenant_id else {}
    state_str = _encode_state(state)

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.modify",
        "access_type": "offline",
        "prompt": "consent",
        "state": state_str,
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    log("INFO", "Starting Google OAuth flow", module="google_oauth", tenant_id=tenant_id)
    return RedirectResponse(url=auth_url)


# Public alias for `/google/login` (no /auth prefix)
@public_router.get("/google/login")
async def google_login_public(request: Request) -> RedirectResponse:
    """Public shortcut to start Google OAuth flow at `/google/login`.

    This delegates to the same logic as `/auth/google/login` but exposes a
    non-prefixed URL as required by some clients.
    """
    return await google_login(request)


@router.get("/google/callback")
async def google_callback(request: Request, db=Depends(get_async_session)) -> JSONResponse:
    """Handle OAuth callback: exchange code for tokens and persist them.

    Expected query params: `code`, `state`.
    """
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code:
        raise HTTPException(status_code=400, detail="Missing 'code' parameter")

    # Recover tenant_id from state (optional)
    tenant_id: Optional[str] = None
    tenant_uuid = None
    if state:
        decoded = _decode_state(state)
        tenant_id = decoded.get("tenant_id")
        # Try to parse tenant_id to UUID for repository lookups
        from uuid import UUID as UUIDType
        try:
            if tenant_id:
                tenant_uuid = UUIDType(tenant_id)
        except Exception:
            tenant_uuid = None

    log("INFO", "Exchanging Google OAuth code for tokens", module="google_oauth", tenant_id=tenant_id)

    token_endpoint = "https://oauth2.googleapis.com/token"
    client_id = os.getenv("GOOGLE_CLIENT_ID") or settings.GOOGLE_CLIENT_ID
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET") or settings.GOOGLE_CLIENT_SECRET
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI") or settings.GOOGLE_REDIRECT_URI

    if not client_id or not client_secret or not redirect_uri:
        log("ERROR", "Google OAuth callback called but config missing", module="google_oauth", tenant_id=tenant_id)
        raise HTTPException(status_code=500, detail="Google OAuth not configured")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(token_endpoint, data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            }, headers={"Accept": "application/json"}, timeout=20.0)
            resp.raise_for_status()
            token_data = resp.json()
    except httpx.HTTPError as exc:
        log("ERROR", f"Google token exchange failed: {exc}", module="google_oauth", tenant_id=tenant_id)
        raise HTTPException(status_code=502, detail="Failed to exchange code for tokens")

    # Extract tokens without logging secrets
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in")
    id_token = token_data.get("id_token")

    # Try to get email from id_token if present (base64 decode payload)
    external_id = None
    try:
        if id_token:
            parts = id_token.split(".")
            if len(parts) >= 2:
                payload_b64 = parts[1] + "=="
                payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode()))
                external_id = payload.get("email") or payload.get("sub")
    except Exception:
        external_id = None

    # Compute expires_at
    expires_at = None
    try:
        if expires_in:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
    except Exception:
        expires_at = None

    # Persist via ExternalTokenRepository (upsert semantics)
    repo = ExternalTokenRepository(db)

    # Build data blob: include refresh_token and expires_at for later refresh
    data_blob = {k: v for k, v in token_data.items() if k not in ("access_token",)}
    if expires_at:
        # serialize as ISO8601
        data_blob["expires_at"] = expires_at.isoformat()

    # Use tenant_id if provided; otherwise leave tenant_id NULL but store external_id
    # Upsert: try to find by tenant+provider or external_id+provider
    from app.db.models import ExternalToken
    existing = None
    if tenant_id:
        rows = await repo.list_by_tenant(tenant_id)
        for r in rows:
            if r.provider == "google":
                existing = r
                break

    if not existing and external_id:
        rows = await repo.list_by_external_id(external_id)
        for r in rows:
            if r.provider == "google":
                existing = r
                break

    if existing:
        await repo.update(existing.id, token=access_token, data=data_blob, external_id=external_id, provider="google", updated_at=datetime.now(timezone.utc))
        log("INFO", "Updated existing ExternalToken for Google OAuth", module="google_oauth", tenant_id=tenant_id, external_id=external_id)
    else:
        # create new record via repository; ensure tenant_id is a valid UUID or leave NULL
        from uuid import UUID as UUIDType
        tenant_uuid = None
        try:
            if tenant_id:
                tenant_uuid = UUIDType(tenant_id)
        except Exception:
            tenant_uuid = None

        # Use repository create (upsert behavior handled above)
        await repo.create(
            tenant_id=tenant_uuid,
            flow_id=None,
            provider="google",
            token=access_token,
            external_id=external_id,
            data=data_blob,
        )
        log("INFO", "Stored Google OAuth tokens via ExternalTokenRepository", module="google_oauth", tenant_id=str(tenant_uuid) if tenant_uuid else None, external_id=external_id)

    return JSONResponse(status_code=200, content={"status": "success", "tenant_id": tenant_id, "external_id": external_id})
