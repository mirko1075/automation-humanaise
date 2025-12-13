"""app/api/admin/monitoring.py
Admin monitoring endpoints for events and audits.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.db.models import RawEvent, NormalizedEvent
from sqlalchemy import text

router = APIRouter(prefix="/admin/monitoring", tags=["admin","monitoring"])


@router.get("/raw_events")
async def list_raw_events(
    tenant_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_session),
):
    """Return raw events, optionally filtered by tenant_id."""
    stmt = select(RawEvent).order_by(RawEvent.created_at.desc()).limit(limit).offset(offset)
    if tenant_id:
        stmt = select(RawEvent).where(RawEvent.tenant_id == tenant_id).order_by(RawEvent.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return {"status": "success", "data": [
        {
            "id": str(r.id),
            "tenant_id": str(r.tenant_id),
            "source": r.source,
            "idempotency_key": r.idempotency_key,
            "processed": r.processed,
            "payload": r.payload,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows
    ]}


@router.get("/discarded_audits")
async def list_discarded_audits(
    tenant_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_session),
):
    """Return audit logs with action = 'preventivi_discarded'."""
    sql = "SELECT id, tenant_id, flow_id, action, details, created_at FROM audit_logs WHERE action='preventivi_discarded'"
    if tenant_id:
        sql += f" AND tenant_id = '{tenant_id}'"
    sql += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
    result = await db.execute(text(sql), {"limit": limit, "offset": offset})
    rows = result.fetchall()
    data = []
    for r in rows:
        data.append({
            "id": str(r[0]),
            "tenant_id": str(r[1]) if r[1] else None,
            "flow_id": r[2],
            "action": r[3],
            "details": r[4],
            "created_at": r[5].isoformat() if r[5] else None,
        })
    return {"status": "success", "data": data}


@router.get("/normalized_events")
async def list_normalized_events(
    tenant_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_session),
):
    """Return normalized events, optionally filtered by tenant_id."""
    stmt = select(NormalizedEvent).order_by(NormalizedEvent.created_at.desc()).limit(limit).offset(offset)
    if tenant_id:
        stmt = select(NormalizedEvent).where(NormalizedEvent.tenant_id == tenant_id).order_by(NormalizedEvent.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return {"status": "success", "data": [
        {
            "id": str(r.id),
            "tenant_id": str(r.tenant_id),
            "flow_id": r.flow_id,
            "event_type": r.event_type,
            "normalized_data": r.normalized_data,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows
    ]}
