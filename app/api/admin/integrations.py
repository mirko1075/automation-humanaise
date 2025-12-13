"""app/api/admin/integrations.py
Admin endpoints to inspect integration events (e.g. OneDrive discovery logs).
"""
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.db.models import IntegrationEvent
from app.db.repositories.integration_event_repository import IntegrationEventRepository
from sqlalchemy import text

router = APIRouter(prefix="/admin/integrations", tags=["admin", "integrations"])


def _parse_iso_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        raise ValueError("Invalid ISO date format; use YYYY-MM-DD or full ISO timestamp")


@router.get("/onedrive/logs")
async def list_onedrive_logs(
    level: Optional[str] = Query(None, description="Filter by level (INFO|WARN|ERROR)"),
    event_type: Optional[str] = Query(None, description="Filter by event_type"),
    since: Optional[str] = Query(None, description="ISO timestamp to filter from (inclusive)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_session),
):
    """Return OneDrive integration events, paginated and filtered."""
    try:
        sdt = _parse_iso_date(since)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    stmt = select(IntegrationEvent).where(IntegrationEvent.integration == "onedrive")
    clauses = []
    if level:
        clauses.append(IntegrationEvent.level == level)
    if event_type:
        clauses.append(IntegrationEvent.event_type == event_type)
    if sdt:
        clauses.append(IntegrationEvent.created_at >= sdt)

    if clauses:
        stmt = stmt.where(and_(*clauses))
    stmt = stmt.order_by(IntegrationEvent.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return {
        "status": "success",
        "data": [
            {
                "id": str(r.id),
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "level": r.level,
                "event_type": r.event_type,
                "message": r.message,
                "context": r.context,
            }
            for r in rows
        ],
    }
