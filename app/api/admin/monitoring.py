"""app/api/admin/monitoring.py
Admin monitoring endpoints for events and audits.
"""
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.db.models import RawEvent, NormalizedEvent
from sqlalchemy import text

router = APIRouter(prefix="/admin/monitoring", tags=["admin", "monitoring"])


def _parse_iso_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        raise ValueError("Invalid ISO date format; use YYYY-MM-DD or full ISO timestamp")


@router.get("/raw_events")
async def list_raw_events(
    tenant_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None, description="ISO start date/time filter (inclusive)"),
    end_date: Optional[str] = Query(None, description="ISO end date/time filter (inclusive)"),
    event_type: Optional[str] = Query(None, description="Filter by event_type present in payload or metadata"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_session),
):
    """Return raw events, optionally filtered by tenant_id, date range, or event_type."""
    # Build base stmt
    stmt = select(RawEvent)
    clauses = []
    if tenant_id:
        clauses.append(RawEvent.tenant_id == tenant_id)
    # Date parsing
    try:
        sdt = _parse_iso_date(start_date)
        edt = _parse_iso_date(end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if sdt:
        clauses.append(RawEvent.created_at >= sdt)
    if edt:
        clauses.append(RawEvent.created_at <= edt)
    if event_type:
        # Use a robust JSONB text extraction using SQL: payload->>'event_type' = :event_type
        # Build a parameterized text clause to avoid SQL injection
        json_clause = text("(payload->> 'event_type') = :event_type")
        stmt = stmt.where(and_(*clauses)) if clauses else stmt
        stmt = stmt.where(json_clause).params(event_type=event_type)
        # we already applied clauses above when setting stmt
        clauses = []
    if clauses:
        stmt = stmt.where(and_(*clauses))
    stmt = stmt.order_by(RawEvent.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return {"status": "success", "data": [
        {
            "id": str(r.id),
            "tenant_id": str(r.tenant_id) if r.tenant_id else None,
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
    """Return audit logs with action = 'preventivi_discarded'. Uses parameterized SQL to avoid injection."""
    sql = "SELECT id, tenant_id, flow_id, action, details, created_at FROM audit_logs WHERE action=:action"
    params = {"action": "preventivi_discarded", "limit": limit, "offset": offset}
    if tenant_id:
        sql += " AND tenant_id = :tenant_id"
        params["tenant_id"] = tenant_id
    sql += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
    result = await db.execute(text(sql), params)
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
    event_type: Optional[str] = Query(None, description="Filter by event_type stored in normalized event"),
    start_date: Optional[str] = Query(None, description="ISO start date/time filter (inclusive)"),
    end_date: Optional[str] = Query(None, description="ISO end date/time filter (inclusive)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_session),
):
    """Return normalized events, optionally filtered by tenant_id, event_type, or date range."""
    try:
        sdt = _parse_iso_date(start_date)
        edt = _parse_iso_date(end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    stmt = select(NormalizedEvent)
    clauses = []
    if tenant_id:
        clauses.append(NormalizedEvent.tenant_id == tenant_id)
    if event_type:
        clauses.append(NormalizedEvent.event_type == event_type)
    if sdt:
        clauses.append(NormalizedEvent.created_at >= sdt)
    if edt:
        clauses.append(NormalizedEvent.created_at <= edt)
    if clauses:
        stmt = stmt.where(and_(*clauses))
    stmt = stmt.order_by(NormalizedEvent.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return {"status": "success", "data": [
        {
            "id": str(r.id),
            "tenant_id": str(r.tenant_id) if r.tenant_id else None,
            "flow_id": r.flow_id,
            "event_type": r.event_type,
            "normalized_data": r.normalized_data,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows
    ]}


@router.get("/audit_trail")
async def audit_trail_by_idempotency(
    idempotency_key: str = Query(..., description="Idempotency key to fetch audit trail for"),
    db: AsyncSession = Depends(get_async_session),
):
    """Return the full audit trail (all audit_logs) for a given idempotency_key."""
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="idempotency_key is required")
    sql = "SELECT id, tenant_id, flow_id, action, details, created_at FROM audit_logs WHERE details->> 'idempotency_key' = :idempotency_key ORDER BY created_at ASC"
    result = await db.execute(text(sql), {"idempotency_key": idempotency_key})
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
