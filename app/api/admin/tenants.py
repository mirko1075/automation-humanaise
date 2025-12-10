# app/api/admin/tenants.py
"""
TenantRegistry for Edilcos Automation Backend.
Provides CRUD APIs for tenants.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from app.db.session import SessionLocal
from app.db.repositories.tenant_repository import TenantRepository
from app.monitoring.logger import log
from app.monitoring.audit import audit_event
import traceback

class TenantCreateDTO(BaseModel):
    name: str
    active_flows: List[str] = Field(default_factory=list)
    gmail_config: Optional[str] = None
    whatsapp_config: Optional[str] = None
    onedrive_config: Optional[str] = None

class TenantUpdateDTO(BaseModel):
    active_flows: Optional[List[str]] = None
    status: Optional[str] = None
    gmail_config: Optional[str] = None
    whatsapp_config: Optional[str] = None
    onedrive_config: Optional[str] = None

class TenantOutDTO(BaseModel):
    id: UUID
    name: str
    active_flows: List[str]
    created_at: str
    status: str
    gmail_config: Optional[str]
    whatsapp_config: Optional[str]
    onedrive_config: Optional[str]

router = APIRouter(prefix="/admin/tenants", tags=["admin"])

@router.get("/")
async def list_tenants() -> List[TenantOutDTO]:
    async with SessionLocal() as db:
        repo = TenantRepository(db)
        tenants = await repo.list()
        return [TenantOutDTO(
            id=t.id,
            name=t.name,
            active_flows=getattr(t, "active_flows", []),
            created_at=str(t.created_at),
            status=getattr(t, "status", "active"),
            gmail_config=getattr(t, "gmail_config", None),
            whatsapp_config=getattr(t, "whatsapp_config", None),
            onedrive_config=getattr(t, "onedrive_config", None)
        ) for t in tenants]

@router.get("/{tenant_id}")
async def get_tenant(tenant_id: UUID) -> TenantOutDTO:
    async with SessionLocal() as db:
        repo = TenantRepository(db)
        tenant = await repo.get(tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        return TenantOutDTO(
            id=tenant.id,
            name=tenant.name,
            active_flows=getattr(tenant, "active_flows", []),
            created_at=str(tenant.created_at),
            status=getattr(tenant, "status", "active"),
            gmail_config=getattr(tenant, "gmail_config", None),
            whatsapp_config=getattr(tenant, "whatsapp_config", None),
            onedrive_config=getattr(tenant, "onedrive_config", None)
        )

@router.post("/")
async def create_tenant(dto: TenantCreateDTO) -> TenantOutDTO:
    async with SessionLocal() as db:
        repo = TenantRepository(db)
        tenant = await repo.create(name=dto.name)
        # Set configs and flows
        for key in ["active_flows", "gmail_config", "whatsapp_config", "onedrive_config"]:
            setattr(tenant, key, getattr(dto, key, None))
        await db.commit()
        await db.refresh(tenant)
        await audit_event("tenant_created", tenant.id, None, dto.dict())
        log("INFO", f"Tenant created: {tenant.name}", module="tenants", tenant_id=tenant.id)
        return TenantOutDTO(
            id=tenant.id,
            name=tenant.name,
            active_flows=getattr(tenant, "active_flows", []),
            created_at=str(tenant.created_at),
            status=getattr(tenant, "status", "active"),
            gmail_config=getattr(tenant, "gmail_config", None),
            whatsapp_config=getattr(tenant, "whatsapp_config", None),
            onedrive_config=getattr(tenant, "onedrive_config", None)
        )

@router.patch("/{tenant_id}")
async def update_tenant(tenant_id: UUID, dto: TenantUpdateDTO) -> TenantOutDTO:
    async with SessionLocal() as db:
        repo = TenantRepository(db)
        tenant = await repo.get(tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        for key, value in dto.dict(exclude_unset=True).items():
            setattr(tenant, key, value)
        await db.commit()
        await db.refresh(tenant)
        await audit_event("tenant_updated", tenant.id, None, dto.dict())
        log("INFO", f"Tenant updated: {tenant.name}", module="tenants", tenant_id=tenant.id)
        return TenantOutDTO(
            id=tenant.id,
            name=tenant.name,
            active_flows=getattr(tenant, "active_flows", []),
            created_at=str(tenant.created_at),
            status=getattr(tenant, "status", "active"),
            gmail_config=getattr(tenant, "gmail_config", None),
            whatsapp_config=getattr(tenant, "whatsapp_config", None),
            onedrive_config=getattr(tenant, "onedrive_config", None)
        )

@router.delete("/{tenant_id}")
async def disable_tenant(tenant_id: UUID) -> dict:
    async with SessionLocal() as db:
        repo = TenantRepository(db)
        tenant = await repo.get(tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        tenant.status = "disabled"
        await db.commit()
        await db.refresh(tenant)
        await audit_event("tenant_disabled", tenant.id, None, {"status": "disabled"})
        log("INFO", f"Tenant disabled: {tenant.name}", module="tenants", tenant_id=tenant.id)
        return {"status": "disabled", "tenant_id": str(tenant.id)}
