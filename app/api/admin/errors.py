# app/api/admin/errors.py
from fastapi import APIRouter, Query
from typing import Optional
from app.db.session import SessionLocal
from app.db.repositories.error_repository import ErrorRepository

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/errors")
async def list_errors(tenant_id: Optional[str] = Query(None), limit: int = 50, offset: int = 0):
    async with SessionLocal() as db:
        repo = ErrorRepository(db)
        if tenant_id:
            return await repo.list_by_tenant(tenant_id, limit=limit, offset=offset)
        return await repo.list_all(limit=limit, offset=offset)
