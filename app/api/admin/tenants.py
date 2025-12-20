# app/api/admin/tenants.py
"""
TenantRegistry for Edilcos Automation Backend.
Provides CRUD APIs for tenants.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
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


class ContactChannelsDTO(BaseModel):
    email: Optional[List[str]] = None
    whatsapp: Optional[List[str]] = None


class TenantUpsertDTO(BaseModel):
    """Payload for idempotent tenant creation/upsert."""
    name: str
    active_flows: Optional[List[str]] = None
    gmail_config: Optional[str] = None
    whatsapp_config: Optional[str] = None
    onedrive_config: Optional[str] = None
    contact_channels: Optional[ContactChannelsDTO] = None
    status: Optional[str] = None

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
        result: list[TenantOutDTO] = []
        for t in tenants:
            active_flows = getattr(t, "active_flows", None) or []
            if not isinstance(active_flows, list):
                # ensure DB values like NULL or string are normalized
                try:
                    active_flows = list(active_flows)
                except Exception:
                    active_flows = []
            result.append(TenantOutDTO(
                id=t.id,
                name=t.name,
                active_flows=active_flows,
                created_at=str(t.created_at),
                status=getattr(t, "status", "active"),
                gmail_config=getattr(t, "gmail_config", None),
                whatsapp_config=getattr(t, "whatsapp_config", None),
                onedrive_config=getattr(t, "onedrive_config", None)
            ))
        return result

@router.get("/{tenant_id}")
async def get_tenant(tenant_id: UUID) -> TenantOutDTO:
    async with SessionLocal() as db:
        repo = TenantRepository(db)
        tenant = await repo.get(tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        active_flows = getattr(tenant, "active_flows", None) or []
        if not isinstance(active_flows, list):
            try:
                active_flows = list(active_flows)
            except Exception:
                active_flows = []
        return TenantOutDTO(
            id=tenant.id,
            name=tenant.name,
            active_flows=active_flows,
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
        active_flows = getattr(tenant, "active_flows", None) or []
        if not isinstance(active_flows, list):
            try:
                active_flows = list(active_flows)
            except Exception:
                active_flows = []
        return TenantOutDTO(
            id=tenant.id,
            name=tenant.name,
            active_flows=active_flows,
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


@router.post("/upsert")
async def upsert_tenant(dto: TenantUpsertDTO) -> TenantOutDTO:
    """Create or update a tenant by `name`. Returns the tenant resource.

    If a tenant with the given `name` exists it will be updated with provided fields,
    otherwise a new tenant will be created. This endpoint is idempotent based on `name`.
    """
    async with SessionLocal() as db:
        repo = TenantRepository(db)
        # Normalize contact channels to dict with lists
        contact_channels: Dict[str, Any] = {}
        if dto.contact_channels:
            if dto.contact_channels.email:
                contact_channels["email"] = dto.contact_channels.email
            if dto.contact_channels.whatsapp:
                contact_channels["whatsapp"] = dto.contact_channels.whatsapp

        payload = {
            "active_flows": dto.active_flows or [],
            "gmail_config": dto.gmail_config,
            "whatsapp_config": dto.whatsapp_config,
            "onedrive_config": dto.onedrive_config,
            "contact_channels": contact_channels,
            "status": dto.status or "active",
        }
        tenant = await repo.upsert_by_name(dto.name, **payload)
        await audit_event("tenant_upserted", tenant.id, None, dto.dict())
        log("INFO", f"Tenant upserted: {tenant.name}", module="tenants", tenant_id=tenant.id)
        active_flows = getattr(tenant, "active_flows", None) or []
        if not isinstance(active_flows, list):
            try:
                active_flows = list(active_flows)
            except Exception:
                active_flows = []
        return TenantOutDTO(
            id=tenant.id,
            name=tenant.name,
            active_flows=active_flows,
            created_at=str(tenant.created_at),
            status=getattr(tenant, "status", "active"),
            gmail_config=getattr(tenant, "gmail_config", None),
            whatsapp_config=getattr(tenant, "whatsapp_config", None),
            onedrive_config=getattr(tenant, "onedrive_config", None)
        )
