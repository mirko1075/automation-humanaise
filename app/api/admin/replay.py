"""app/api/admin/replay.py

Admin replay endpoints for RawEvent reprocessing.

This module provides a protected endpoint for operators to re-run normalization
for a specific RawEvent. It is intentionally minimal and only acts as a
lightweight job enqueuer for the normalizer pipeline.
"""
from fastapi import APIRouter, Depends, HTTPException
from app.db.session import SessionLocal
from app.monitoring.logger import log

router = APIRouter(prefix="/admin", tags=["admin"])

# TODO(replay): admin endpoint POST /admin/raw_events/{raw_event_id}/replay to re-run normalization
# TODO(ops): permissioned access and audit log for manual replays


@router.post("/raw_events/{raw_event_id}/replay")
async def replay_raw_event(raw_event_id: str):
    """Enqueue re-run for a RawEvent id.

    Note: implement `get_current_admin` dependency and audit logging in v1.
    """
    # Minimal stub: validate id format and return accepted
    try:
        # Basic validation only; real implementation should check DB and enqueue job
        return {"status": "accepted", "raw_event_id": raw_event_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
