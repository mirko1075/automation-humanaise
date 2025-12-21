"""Admin messages router.

Exposes read-only inbox endpoints for RawEvent and associated normalized data.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.db import models

router = APIRouter(prefix="/admin/messages", tags=["admin", "messages"])


@router.get("")
async def list_messages(limit: int = Query(50, ge=1, le=500), only_pending: Optional[bool] = Query(False), db: AsyncSession = Depends(get_async_session)):
    stmt = select(models.RawEvent)
    if only_pending:
        stmt = stmt.where(models.RawEvent.processed == False)
    stmt = stmt.order_by(models.RawEvent.created_at.desc()).limit(limit)
    res = await db.execute(stmt)
    rows = res.scalars().all()
    out = []
    for r in rows:
        out.append({
            "raw_event_id": str(r.id),
            "source": r.source,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "processed": r.processed,
            "tenant_id": str(r.tenant_id) if r.tenant_id else None,
        })
    # TODO(console): aggiungere UI admin
    # TODO(replay): endpoint reprocess manuale
    # TODO(monitoring): metriche e alert automatici
    return {"status": "success", "data": out}


@router.get("/{raw_event_id}")
async def get_message(raw_event_id: str, db: AsyncSession = Depends(get_async_session)):
    stmt = select(models.RawEvent).where(models.RawEvent.id == raw_event_id)
    res = await db.execute(stmt)
    r = res.scalars().first()
    if not r:
        raise HTTPException(status_code=404, detail="RawEvent not found")

    norm = None
    try:
        if isinstance(r.payload, dict) and r.payload.get("normalized_event_id"):
            nstmt = select(models.NormalizedEvent).where(models.NormalizedEvent.id == r.payload.get("normalized_event_id"))
            nres = await db.execute(nstmt)
            norm = nres.scalars().first()
    except Exception:
        norm = None

    references = {}
    if norm and isinstance(norm.normalized_data, dict):
        references["preventivo_id"] = norm.normalized_data.get("preventivo_id")
        references["customer_id"] = norm.normalized_data.get("customer_id")

    return {
        "status": "success",
        "data": {
            "raw_event": {"id": str(r.id), "payload": r.payload, "created_at": r.created_at.isoformat() if r.created_at else None},
            "normalized_event": (lambda n: {"id": str(n.id), "event_type": n.event_type, "status": n.status, "normalized_data": n.normalized_data} if n else None)(norm),
            "references": references,
        }
    }
