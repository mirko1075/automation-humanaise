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

router = APIRouter(prefix="/admin", tags=["health"])


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
    return {"status": "ready"}
