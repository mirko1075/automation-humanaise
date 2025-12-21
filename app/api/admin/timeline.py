"""Admin timeline endpoints.

Provide read-only timeline retrieval from `AuditLog` for admin console and UI.

Endpoints:
- GET /admin/timeline?raw_event_id=...&request_id=...&limit=...
- GET /admin/timeline/{audit_id}

This module is read-only and intended for operator observability. It does
not alter business state.
"""
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.db.models import AuditLog
from app.monitoring.logger import log

router = APIRouter(prefix="/admin", tags=["admin", "timeline"])


@router.get("/timeline")
async def list_timeline(
    raw_event_id: Optional[str] = Query(None),
    request_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_async_session),
):
    """Return audit timeline entries filtered by `raw_event_id` or `request_id`.

    Searches `AuditLog.details` JSON for these keys. This is best-effort and
    may be slow on large tables; consider adding indexed summary columns later.
    """
    if not raw_event_id and not request_id:
        raise HTTPException(status_code=400, detail="Provide raw_event_id or request_id")

    try:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        # Filter by JSON details if supported; fallback: match by stringified details
        clauses = []
        if raw_event_id:
            clauses.append(AuditLog.details["raw_event_id"].astext == raw_event_id)
        if request_id:
            clauses.append(AuditLog.details["request_id"].astext == request_id)

        if clauses:
            stmt = select(AuditLog).where(or_(*clauses)).order_by(AuditLog.created_at.desc()).limit(limit)

        res = await db.execute(stmt)
        rows = res.scalars().all()
        out = []
        for r in rows:
            out.append({
                "id": str(r.id),
                "action": r.action,
                "tenant_id": str(r.tenant_id) if r.tenant_id else None,
                "flow_id": r.flow_id,
                "details": r.details,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })
        return {"status": "success", "data": out}
    except Exception as exc:
        log("ERROR", "timeline.query_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Timeline query failed")



@router.get("/timeline/search")
async def search_timeline(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=1000),
    from_ts: Optional[datetime] = Query(None, description="Start timestamp (inclusive) in ISO format"),
    to_ts: Optional[datetime] = Query(None, description="End timestamp (inclusive) in ISO format"),
    action: Optional[str] = Query(None, description="Filter by audit action"),
    tenant_id: Optional[str] = Query(None, description="Filter by tenant_id"),
    db: AsyncSession = Depends(get_async_session),
):
    """Paginated search over AuditLog with optional filters.

    Filters supported: date range (`from_ts`, `to_ts`), `action`, `tenant_id`.
    Returns items (list), total, page and per_page.
    """
    try:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
        filters = []
        if from_ts:
            # Normalize timezone-aware datetimes to UTC naive for DB comparisons
            if from_ts.tzinfo is not None:
                from_ts = from_ts.astimezone(timezone.utc).replace(tzinfo=None)
            filters.append(AuditLog.created_at >= from_ts)
        if to_ts:
            if to_ts.tzinfo is not None:
                to_ts = to_ts.astimezone(timezone.utc).replace(tzinfo=None)
            filters.append(AuditLog.created_at <= to_ts)
        if action:
            filters.append(AuditLog.action == action)
        if tenant_id:
            filters.append(AuditLog.tenant_id == tenant_id)

        if filters:
            stmt = stmt.where(and_(*filters))

        # total count
        count_stmt = select(func.count()).select_from(AuditLog)
        if filters:
            count_stmt = count_stmt.where(and_(*filters))
        count_res = await db.execute(count_stmt)
        total = int(count_res.scalar() or 0)

        offset = (page - 1) * per_page
        stmt = stmt.offset(offset).limit(per_page)
        res = await db.execute(stmt)
        rows = res.scalars().all()

        items = []
        for r in rows:
            items.append({
                "id": str(r.id),
                "action": r.action,
                "tenant_id": str(r.tenant_id) if r.tenant_id else None,
                "flow_id": r.flow_id,
                "details": r.details,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })

        return {
            "status": "success",
            "data": {
                "items": items,
                "total": total,
                "page": page,
                "per_page": per_page,
            },
        }
    except Exception as exc:
        log("ERROR", "timeline.search_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Timeline search failed")


@router.get("/timeline/{audit_id}")
async def get_timeline_entry(audit_id: str, db: AsyncSession = Depends(get_async_session)):
    """Return a single AuditLog entry by id."""
    res = await db.execute(select(AuditLog).where(AuditLog.id == audit_id))
    r = res.scalars().first()
    if not r:
        raise HTTPException(status_code=404, detail="Audit entry not found")
    return {
        "status": "success",
        "data": {
            "id": str(r.id),
            "action": r.action,
            "tenant_id": str(r.tenant_id) if r.tenant_id else None,
            "flow_id": r.flow_id,
            "actor": r.actor,
            "details": r.details,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        },
    }

# TODO(console): endpoint admin per timeline raw_event
# TODO(console): UI timeline per request_id
# TODO(monitoring): metriche aggregate per step
