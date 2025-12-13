"""# app/api/auth/google_oauth.py
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from typing import Any, Dict

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/google/callback")
async def google_callback(request: Request) -> Dict[str, Any]:
    """Simple placeholder for Google OAuth callback.

    This endpoint exists to satisfy redirect URI configuration in
    Google Cloud Console. It should be replaced with a full OAuth
    exchange handler (code + state validation) when implementing
    authentication flows.

    Returns:
        A JSON response acknowledging receipt of the OAuth callback.
    """
    # Minimal validation: ensure `code` query param exists
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing 'code' query parameter")

    return JSONResponse(status_code=200, content={"status": "ok", "note": "OAuth callback placeholder"})
