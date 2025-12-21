# app/api/admin/health.py
"""
Health endpoints for shallow and deep readiness checks.
"""
from fastapi import APIRouter, HTTPException, Depends
from starlette.status import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import check_db_ready, get_async_session
from app.db.repositories.tenant_repository import TenantRepository
from app.file_access.registry import get_file_provider
from app.config import settings
import app.integrations.onedrive_client as onedrive_client_module
from typing import Dict, Any

router = APIRouter(prefix="/admin", tags=["health"])

# Expose symbol for test monkeypatching
OneDriveClient = onedrive_client_module.OneDriveClient


@router.get("/health", status_code=HTTP_200_OK)
async def health() -> dict:
    """Shallow health endpoint."""
    return {"status": "ok", "version": "1.0.0"}


@router.get("/health/deep", status_code=HTTP_200_OK)
async def health_deep(db: AsyncSession = Depends(get_async_session)) -> dict:
    """
    Deep health endpoint performing database connectivity and file provider checks.
    
    Checks:
    - Database connectivity
    - File provider health for all active tenants
    """
    # Check database
    db_ready = await check_db_ready()
    if not db_ready:
        raise HTTPException(status_code=HTTP_503_SERVICE_UNAVAILABLE, detail="Database not ready")
    
    # Check file providers
    tenant_repo = TenantRepository(db)
    tenants = await tenant_repo.list_active()
    
    provider_checks = []
    for tenant in tenants:
        if tenant.file_provider:
            try:
                provider = get_file_provider(tenant)
                health_result = await provider.health_check()
                provider_checks.append({
                    "tenant_id": str(tenant.id),
                    "tenant_name": tenant.name,
                    "provider": tenant.file_provider,
                    "healthy": health_result.get("healthy", False),
                    "message": health_result.get("message", ""),
                    "details": health_result.get("details", {})
                })
            except Exception as exc:
                provider_checks.append({
                    "tenant_id": str(tenant.id),
                    "tenant_name": tenant.name,
                    "provider": tenant.file_provider,
                    "healthy": False,
                    "message": f"Provider initialization failed: {exc}",
                    "error": str(exc)
                })
    
    # Determine overall health
    all_providers_healthy = all(check["healthy"] for check in provider_checks)
    
    result = {
        "status": "ready" if all_providers_healthy else "degraded",
        "database": {"healthy": db_ready, "message": "Database ready"},
        "file_providers": {
            "total": len(provider_checks),
            "healthy": sum(1 for c in provider_checks if c["healthy"]),
            "unhealthy": sum(1 for c in provider_checks if not c["healthy"]),
            "checks": provider_checks
        }
    }
    
    if not all_providers_healthy:
        result["warnings"] = [
            f"Tenant {c['tenant_name']} ({c['provider']}): {c['message']}"
            for c in provider_checks if not c["healthy"]
        ]
    
    return result


@router.get("/ready", status_code=HTTP_200_OK)
async def ready() -> dict:
    """Alias for deep readiness to match deployment health checks."""
    ready = await check_db_ready()
    if not ready:
        raise HTTPException(status_code=HTTP_503_SERVICE_UNAVAILABLE, detail="Not ready")
    # Also check OneDrive readiness using the onedrive healthcheck logic.
    try:
        # Import and call the healthcheck function defined in this module
        one_result = await onedrive_healthcheck()
        if one_result.get("status") != "ok":
            # Provide a clear reason in the payload and return 503
            raise HTTPException(status_code=HTTP_503_SERVICE_UNAVAILABLE, detail={
                "reason": "onedrive_not_ready",
                "details": one_result
            })
    except HTTPException:
        # Propagate HTTPExceptions raised inside the healthcheck
        raise
    except Exception as exc:
        # Fail fast — report error
        raise HTTPException(status_code=HTTP_503_SERVICE_UNAVAILABLE, detail={
            "reason": "onedrive_check_failed",
            "error": str(exc)
        })

    return {"status": "ready"}


@router.get("/health/onedrive", status_code=HTTP_200_OK)
async def onedrive_healthcheck() -> Dict[str, Any]:
    """
    OneDrive/SharePoint connectivity health check for operators.

    Returns a structured JSON containing per-step status for:
      - auth: token acquisition
      - drive: GET /drives/{drive_id}
      - root: GET /drives/{drive_id}/root
      - children: GET /drives/{drive_id}/root/children
      - write: optional create+delete folder when `ONEDRIVE_HEALTHCHECK_WRITE=true`
    """
    result: Dict[str, Any] = {
        "status": "ok",
        "steps": {
            "auth": {"ok": False},
            "drive": {"ok": False},
            "root": {"ok": False},
            "children": {"ok": False},
            "write": {"ok": None, "skipped": True},
        },
    }

    drive_id = settings.MS_DRIVE_ID
    if not drive_id:
        raise HTTPException(status_code=500, detail="MS_DRIVE_ID is not configured")

    # Auth step: rely on client's OAuth provider to ensure token
    # Candidate client classes to try: prefer integration module (tests may patch this),
    # then the module-level alias (tests may patch that instead). For each candidate
    # try to instantiate and perform the auth step; choose the first that succeeds.
    candidates = []
    try:
        candidates.append(onedrive_client_module.OneDriveClient)
    except Exception:
        pass
    alias = globals().get("OneDriveClient")
    if alias and alias not in candidates:
        candidates.append(alias)

    client = None
    auth_error_messages = []
    for cand in candidates:
        try:
            inst = cand()
        except Exception as exc:
            auth_error_messages.append(str(exc))
            continue
        try:
            auth_obj = getattr(inst, "auth", None)
            auth_provider = getattr(auth_obj, "_ensure_token", None) if auth_obj is not None else None
            if callable(auth_provider):
                await auth_provider()
            result["steps"]["auth"]["ok"] = True
            client = inst
            break
        except Exception as exc:
            auth_error_messages.append(str(exc))
            continue

    if client is None:
        result["status"] = "fail"
        result["steps"]["auth"]["ok"] = False
        result["steps"]["auth"]["error"] = "; ".join(auth_error_messages) or "auth_failed"
        return result

    # Drive metadata
    try:
        drive = await client.get_drive(drive_id)
        result["steps"]["drive"]["ok"] = True
        result["steps"]["drive"]["data"] = {"id": drive.get("id"), "driveType": drive.get("driveType")}
    except Exception as exc:
        result["status"] = "fail"
        result["steps"]["drive"]["ok"] = False
        result["steps"]["drive"]["error"] = str(exc)
        return result

    # Root
    try:
        _ = await client.get_drive_root(drive_id)
        result["steps"]["root"]["ok"] = True
    except Exception as exc:
        result["status"] = "fail"
        result["steps"]["root"]["ok"] = False
        result["steps"]["root"]["error"] = str(exc)
        return result

    # Children
    try:
        children = await client.list_drive_root_children(drive_id)
        result["steps"]["children"]["ok"] = True
        result["steps"]["children"]["count"] = len(children.get("value", [])) if isinstance(children, dict) else None
    except Exception as exc:
        result["status"] = "fail"
        result["steps"]["children"]["ok"] = False
        result["steps"]["children"]["error"] = str(exc)
        return result

    # Optional write test
    if settings.ONEDRIVE_HEALTHCHECK_WRITE:
        result["steps"]["write"]["skipped"] = False
        try:
            folder = await client.create_folder(drive_id, parent_item_id="root", name="_healthcheck")
            await client.delete_item(drive_id, folder.get("id"))
            result["steps"]["write"]["ok"] = True
        except Exception as exc:
            result["status"] = "fail"
            result["steps"]["write"]["ok"] = False
            result["steps"]["write"]["error"] = str(exc)
            return result

    return result
