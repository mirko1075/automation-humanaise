# app/api/admin/monitoring.py
"""
Admin monitoring endpoints for the Gmail -> Preventivi pipeline.

Read-only monitoring and a pull-based alert checker.

Endpoints:
- GET /admin/monitoring/overview
- GET /admin/monitoring/stalled
- GET /admin/monitoring/errors
- POST /admin/monitoring/check-alerts

This module must not write to the DB. Queries use AsyncSession from
`app.db.session.get_async_session` and read tables: RawEvent, ReceivedEmail,
ErrorLog, AuditLog.

# TODO(monitoring): expose a minimal operational overview endpoint (status, last event time, counters)
# TODO(monitoring): track number of raw events received, processed, failed, and pending
# TODO(monitoring): track last successful processing timestamp per source (email, webhook, api)
# TODO(console): build minimal admin UI consuming these endpoints

# Operational TODOs (added by automation):
# TODO(monitoring): detect stalled raw events (processed = false for too long)
# TODO(alerting): raise CRITICAL alert when stalled events exceed threshold
# TODO(alerting): raise WARNING alert when processing backlog grows abnormally
# TODO(observability): persist normalization and dispatch failures with reason codes
# TODO(observability): distinguish retryable vs non-retryable failures
# TODO(observability): correlate raw_event_id across webhook → normalizer → dispatcher
# TODO(ops): add admin endpoint to manually reprocess a stalled raw_event
# TODO(ops): add admin endpoint to mark raw_event as ignored/skipped
# TODO(console): show live status of active modules and flows
# TODO(monitoring): add per-tenant metrics and thresholds (future)
# TODO(alerting): allow alert thresholds to be configured via env or DB
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, List

try:
    import structlog
    logger = structlog.get_logger()
except Exception:  # pragma: no cover - best-effort fallback when deps missing
    import logging

    logger = logging.getLogger("app.monitoring")
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.db import models

router = APIRouter(prefix="/admin/monitoring", tags=["admin", "monitoring"])


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/overview")
async def overview(db: AsyncSession = Depends(get_async_session)) -> Any:
    """Return high-level counters and recent timestamps.

    # TODO(monitoring): refine status thresholds per tenant
    # TODO(observability): expose per-tenant counters
    """
    now = _now_utc()
    since_24h = now - timedelta(hours=24)
    # Database columns use naive UTC datetimes (datetime.utcnow). asyncpg/Postgres
    # will raise when comparing offset-aware datetimes with naive ones. Convert
    # the cutoff to a naive UTC datetime for queries.
    if since_24h.tzinfo is not None:
        since_24h_query = since_24h.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        since_24h_query = since_24h

    # Counters in last 24h
    # TODO(monitoring): track number of raw events received, processed, failed, and pending
    raw_received_q = select(func.count()).select_from(models.RawEvent).where(models.RawEvent.created_at >= since_24h_query)
    raw_processed_q = select(func.count()).select_from(models.RawEvent).where(
        and_(models.RawEvent.created_at >= since_24h_query, models.RawEvent.processed == True)
    )
    raw_pending_q = select(func.count()).select_from(models.RawEvent).where(
        and_(models.RawEvent.created_at >= since_24h_query, models.RawEvent.processed == False)
    )

    # errors: ReceivedEmail.outcome='error' OR ErrorLog entries
    raw_errors_q = select(func.count()).select_from(models.ReceivedEmail).where(
        and_(models.ReceivedEmail.created_at >= since_24h_query, models.ReceivedEmail.outcome == 'error')
    )
    error_logs_q = select(func.count()).select_from(models.ErrorLog).where(models.ErrorLog.created_at >= since_24h_query)

    # last event per source (at least gmail)
    # TODO(monitoring): track last successful processing timestamp per source (email, webhook, api)
    last_gmail_q = select(func.max(models.RawEvent.created_at)).where(models.RawEvent.source == 'gmail')

    try:
        results = await db.execute(raw_received_q)
        raw_received = results.scalar() or 0

        results = await db.execute(raw_processed_q)
        raw_processed = results.scalar() or 0

        results = await db.execute(raw_pending_q)
        raw_pending = results.scalar() or 0

        results = await db.execute(raw_errors_q)
        raw_errors_recev = results.scalar() or 0

        results = await db.execute(error_logs_q)
        error_logs_count = results.scalar() or 0

        results = await db.execute(last_gmail_q)
        last_gmail = results.scalar()
    except Exception as e:
        logger.exception("monitoring.overview.query_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Monitoring query failed")

    total_errors = (raw_errors_recev or 0) + (error_logs_count or 0)

    # Very small rule for status aggregation
    # TODO(alerting): classify alerts by severity (INFO, WARNING, CRITICAL)
    status = "ok"
    if total_errors > 0 or raw_pending > 100:
        status = "warning"
    if raw_pending > 1000 or total_errors > 100:
        status = "critical"

    # Build a minimal alerts list based on thresholds (keeps behavior simple)
    alerts: List[dict] = []
    if raw_pending > 1000:
        alerts.append({"level": "CRITICAL", "reason": f"pending_raw_events={raw_pending} > 1000"})
    elif raw_pending > 100:
        alerts.append({"level": "WARNING", "reason": f"pending_raw_events={raw_pending} > 100"})

    if total_errors > 100:
        alerts.append({"level": "CRITICAL", "reason": f"total_errors={total_errors} > 100"})
    elif total_errors > 0:
        alerts.append({"level": "WARNING", "reason": f"total_errors={total_errors} > 0"})

    # Summary payload returned to caller
    summary = {
        "status": status,
        "generated_at": now.isoformat(),
        "counters_last_24h": {
            "raw_received": raw_received,
            "raw_processed": raw_processed,
            "raw_pending": raw_pending,
            "raw_errors": raw_errors_recev,
            "error_logs": error_logs_count,
            "total_errors": total_errors,
        },
        "last_event_at": last_gmail.isoformat() if last_gmail else None,
        "alerts_sent": [],
    }

    # Emit notifications if any alerts found
    # TODO(alerting): add alert deduplication window to avoid repeated notifications
    # TODO(alerting): support multiple alert channels (slack, email, webhook) via config
    if alerts:
        messages = [f"[{a['level']}] {a['reason']}" for a in alerts]
        body = "\n".join(messages)

        # Use async Slack alert helper if available
        try:
            from app.monitoring.slack_alerts import send_slack_alert

            try:
                await send_slack_alert(body, module="monitoring.check_alerts")
                summary["alerts_sent"].append({"via": "slack", "body": body})
            except Exception as e:
                logger.exception("monitoring.check_alerts.slack_failed", error=str(e))
        except Exception as e:
            logger.exception("monitoring.check_alerts.notify_helper_missing", error=str(e))

    return summary


@router.get("/stalled")
async def list_stalled_raw_events(
    older_than_minutes: int = Query(60, ge=1),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_async_session),
):
    """List RawEvent rows that are unprocessed and older than `older_than_minutes`."""
    cutoff = _now_utc() - timedelta(minutes=older_than_minutes)
    # DB stores naive datetimes; convert to naive
    if cutoff.tzinfo is not None:
        cutoff_query = cutoff.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        cutoff_query = cutoff
    stmt = select(models.RawEvent).where(and_(models.RawEvent.processed == False, models.RawEvent.created_at <= cutoff_query))
    stmt = stmt.order_by(models.RawEvent.created_at.desc()).limit(limit)
    res = await db.execute(stmt)
    rows = res.scalars().all()
    return {"status": "success", "data": [{"id": str(r.id), "created_at": r.created_at.isoformat() if r.created_at else None, "source": r.source, "tenant_id": str(r.tenant_id) if r.tenant_id else None} for r in rows]}


@router.get("/errors")
async def list_recent_errors(
    since_hours: int = Query(24, ge=1),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_async_session),
):
    """Return recent ErrorLog entries and ReceivedEmail outcomes marked as 'error'."""
    cutoff = _now_utc() - timedelta(hours=since_hours)
    if cutoff.tzinfo is not None:
        cutoff_query = cutoff.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        cutoff_query = cutoff

    # ErrorLog entries
    err_stmt = select(models.ErrorLog).where(models.ErrorLog.created_at >= cutoff_query).order_by(models.ErrorLog.created_at.desc()).limit(limit)
    res = await db.execute(err_stmt)
    errs = res.scalars().all()
    # Recent ReceivedEmail with outcome='error'
    rec_stmt = select(models.ReceivedEmail).where(and_(models.ReceivedEmail.created_at >= cutoff_query, models.ReceivedEmail.outcome == 'error')).order_by(models.ReceivedEmail.created_at.desc()).limit(limit)
    rres = await db.execute(rec_stmt)
    recs = rres.scalars().all()

    data = {
        "error_logs": [
            {"id": str(e.id), "message": e.message, "created_at": e.created_at.isoformat() if e.created_at else None} for e in errs
        ],
        "received_email_errors": [
            {"id": str(r.id), "identifier": r.identifier, "created_at": r.created_at.isoformat() if r.created_at else None, "details": r.raw_payload} for r in recs
        ]
    }
    return {"status": "success", "data": data}


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
    from sqlalchemy import String as _String, cast as _cast, text

    stmt = select(models.RawEvent)
    clauses = []
    if tenant_id:
        norm_param = tenant_id.replace('-', '').lower()
        clauses.append(func.replace(_cast(models.RawEvent.tenant_id, _String), '-', '') == norm_param)

    try:
        sdt = _parse_iso_date(start_date)
        edt = _parse_iso_date(end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if sdt:
        clauses.append(models.RawEvent.created_at >= sdt)
    if edt:
        clauses.append(models.RawEvent.created_at <= edt)

    if event_type:
        dialect_name = None
        try:
            dialect_name = db.bind.dialect.name  # type: ignore[attr-defined]
        except Exception:
            dialect_name = None

        if dialect_name == "postgresql":
            json_clause = text("(payload->> 'event_type') = :event_type")
            stmt = stmt.where(and_(*clauses)) if clauses else stmt
            stmt = stmt.where(json_clause).params(event_type=event_type)
        else:
            stmt = stmt.where(and_(*clauses)) if clauses else stmt
            stmt = stmt.where(func.json_extract(models.RawEvent.payload, "$.event_type") == event_type)
    if clauses:
        stmt = stmt.where(and_(*clauses))
    stmt = stmt.order_by(models.RawEvent.created_at.desc()).limit(limit).offset(offset)
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
    from sqlalchemy import String as _String, cast as _cast

    stmt = select(models.AuditLog)
    clauses = [models.AuditLog.action == "preventivi_discarded"]
    if tenant_id:
        norm_param = tenant_id.replace('-', '').lower()
        clauses.append(func.replace(_cast(models.AuditLog.tenant_id, _String), '-', '') == norm_param)

    if clauses:
        stmt = stmt.where(and_(*clauses))
    stmt = stmt.order_by(models.AuditLog.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return {"status": "success", "data": [
        {
            "id": str(r.id),
            "tenant_id": str(r.tenant_id) if r.tenant_id else None,
            "flow_id": r.flow_id,
            "action": r.action,
            "details": r.details,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows
    ]}


@router.get("/gmail_events")
async def list_gmail_events(
    processed: Optional[bool] = Query(None, description="Filter by processed status (true=accepted, false=scartati)"),
    start_date: Optional[str] = Query(None, description="ISO start date/time filter (inclusive)"),
    end_date: Optional[str] = Query(None, description="ISO end date/time filter (inclusive)"),
    event_type: Optional[str] = Query(None, description="Filter by event_type present in payload"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_session),
):
    """Return Gmail RawEvents filtered by processed status and event_type."""
    from sqlalchemy import text

    stmt = select(models.RawEvent)
    clauses = []
    try:
        sdt = _parse_iso_date(start_date)
        edt = _parse_iso_date(end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if sdt:
        clauses.append(models.RawEvent.created_at >= sdt)
    if edt:
        clauses.append(models.RawEvent.created_at <= edt)
    if processed is not None:
        clauses.append(models.RawEvent.processed == processed)
    if event_type:
        # dialect-aware JSON extraction
        dialect_name = None
        try:
            dialect_name = db.bind.dialect.name  # type: ignore[attr-defined]
        except Exception:
            dialect_name = None
        if dialect_name == "postgresql":
            stmt = stmt.where(and_(*clauses)) if clauses else stmt
            stmt = stmt.where(text("(payload->> 'event_type') = :event_type")).params(event_type=event_type)
            clauses = []
        else:
            stmt = stmt.where(and_(*clauses)) if clauses else stmt
            stmt = stmt.where(func.json_extract(models.RawEvent.payload, "$.event_type") == event_type)
            clauses = []
    if clauses:
        stmt = stmt.where(and_(*clauses))
    # only Gmail source
    stmt = stmt.where(models.RawEvent.source == "gmail")
    stmt = stmt.order_by(models.RawEvent.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return {"status": "success", "data": [
        {
            "id": str(r.id),
            "tenant_id": str(r.tenant_id) if r.tenant_id else None,
            "processed": r.processed,
            "payload": r.payload,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows
    ]}


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
    stmt = select(models.NormalizedEvent)
    try:
        sdt = _parse_iso_date(start_date)
        edt = _parse_iso_date(end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    clauses = []
    if tenant_id:
        norm_param = tenant_id.replace('-', '').lower()
        from sqlalchemy import String as _String, cast as _cast

        clauses.append(func.replace(_cast(models.NormalizedEvent.tenant_id, _String), '-', '') == norm_param)
    if event_type:
        clauses.append(models.NormalizedEvent.event_type == event_type)
    if sdt:
        clauses.append(models.NormalizedEvent.created_at >= sdt)
    if edt:
        clauses.append(models.NormalizedEvent.created_at <= edt)
    if clauses:
        stmt = stmt.where(and_(*clauses))
    stmt = stmt.order_by(models.NormalizedEvent.created_at.desc()).limit(limit).offset(offset)
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
    # Dialect-aware JSON extraction for idempotency_key inside details JSON
    dialect_name = None
    try:
        dialect_name = db.bind.dialect.name  # type: ignore[attr-defined]
    except Exception:
        dialect_name = None

    stmt = select(models.AuditLog)
    if dialect_name == "postgresql":
        from sqlalchemy import text

        stmt = stmt.where(text("details->> 'idempotency_key' = :idempotency_key")).params(idempotency_key=idempotency_key)
    else:
        stmt = stmt.where(func.json_extract(models.AuditLog.details, "$.idempotency_key") == idempotency_key)
    stmt = stmt.order_by(models.AuditLog.created_at.asc())
    result = await db.execute(stmt)
    rows = result.scalars().all()
    data = []
    for r in rows:
        data.append({
            "id": str(r.id),
            "tenant_id": str(r.tenant_id) if r.tenant_id else None,
            "flow_id": r.flow_id,
            "action": r.action,
            "details": r.details,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return {"status": "success", "data": data}
    


@router.get("/messages")
async def list_admin_messages(
    limit: int = Query(50, ge=1, le=500),
    only_pending: Optional[bool] = Query(False, description="If true, only return raw events where processed=false"),
    db: AsyncSession = Depends(get_async_session),
):
    """Return RawEvent list joined with NormalizedEvent (if exists).

    Read-only. Results ordered by RawEvent.created_at DESC.
    """
    from sqlalchemy import outerjoin

    stmt = select(models.RawEvent)
    if only_pending:
        stmt = stmt.where(models.RawEvent.processed == False)
    stmt = stmt.order_by(models.RawEvent.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    data = []
    for r in rows:
        # try to find a normalized event for this raw event by idempotency or payload link
        norm = None
        try:
            ne_stmt = select(models.NormalizedEvent).where(models.NormalizedEvent.id == func.json_extract(r.payload, "$.normalized_event_id"))
            nr = await db.execute(ne_stmt)
            norm = nr.scalars().first()
        except Exception:
            # best-effort: some payloads won't have normalized id; skip
            norm = None

        outcome = None
        if norm:
            outcome = norm.status

        # attempt to surface any error in payload or audit details
        error = None
        try:
            if isinstance(r.payload, dict) and r.payload.get("error"):
                error = r.payload.get("error")
        except Exception:
            error = None

        data.append({
            "raw_event_id": str(r.id),
            "source": r.source,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "processed": r.processed,
            "outcome": outcome,
            "tenant_id": str(r.tenant_id) if r.tenant_id else None,
            "error": error,
        })

    # TODO(console): aggiungere UI admin
    # TODO(replay): endpoint reprocess manuale
    # TODO(monitoring): metriche e alert automatici

    return {"status": "success", "data": data}


@router.get("/messages/{raw_event_id}")
async def get_admin_message(raw_event_id: str, db: AsyncSession = Depends(get_async_session)):
    """Return RawEvent and associated NormalizedEvent (if any) with references to preventivo/customer when present."""
    try:
        stmt = select(models.RawEvent).where(models.RawEvent.id == raw_event_id)
        res = await db.execute(stmt)
        r = res.scalars().first()
        if not r:
            raise HTTPException(status_code=404, detail="RawEvent not found")

        # try to locate normalized event by id in payload
        norm = None
        try:
            ne_id = None
            if isinstance(r.payload, dict):
                ne_id = r.payload.get("normalized_event_id")
            if ne_id:
                nstmt = select(models.NormalizedEvent).where(models.NormalizedEvent.id == ne_id)
                nres = await db.execute(nstmt)
                norm = nres.scalars().first()
        except Exception:
            norm = None

        # attempt to surface linked preventivo or customer ids in normalized_data
        preventivo_ref = None
        customer_ref = None
        if norm and isinstance(norm.normalized_data, dict):
            preventivo_ref = norm.normalized_data.get("preventivo_id")
            customer_ref = norm.normalized_data.get("customer_id")

        return {
            "status": "success",
            "data": {
                "raw_event": {
                    "id": str(r.id),
                    "tenant_id": str(r.tenant_id) if r.tenant_id else None,
                    "source": r.source,
                    "payload": r.payload,
                    "processed": r.processed,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                },
                "normalized_event": {
                    "id": str(norm.id),
                    "event_type": norm.event_type,
                    "status": norm.status,
                    "normalized_data": norm.normalized_data,
                    "created_at": norm.created_at.isoformat() if norm.created_at else None,
                } if norm else None,
                "references": {
                    "preventivo_id": preventivo_ref,
                    "customer_id": customer_ref,
                },
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("monitoring.get_admin_message.failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch message details")
    clauses = [AuditLog.action == "preventivi_discarded"]
    if tenant_id:
        norm_param = tenant_id.replace('-', '').lower()
        clauses.append(func.replace(_cast(AuditLog.tenant_id, _String), '-', '') == norm_param)

    if clauses:
        stmt = stmt.where(and_(*clauses))
    stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return {"status": "success", "data": [
        {
            "id": str(r.id),
            "tenant_id": str(r.tenant_id) if r.tenant_id else None,
            "flow_id": r.flow_id,
            "action": r.action,
            "details": r.details,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows
    ]}


@router.get("/gmail_events")
async def list_gmail_events(
    processed: Optional[bool] = Query(None, description="Filter by processed status (true=accepted, false=scartati)"),
    start_date: Optional[str] = Query(None, description="ISO start date/time filter (inclusive)"),
    end_date: Optional[str] = Query(None, description="ISO end date/time filter (inclusive)"),
    event_type: Optional[str] = Query(None, description="Filter by event_type present in payload"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_session),
):
    """Return Gmail RawEvents filtered by processed status and event_type."""
    stmt = select(RawEvent)
    clauses = []
    try:
        sdt = _parse_iso_date(start_date)
        edt = _parse_iso_date(end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if sdt:
        clauses.append(RawEvent.created_at >= sdt)
    if edt:
        clauses.append(RawEvent.created_at <= edt)
    if processed is not None:
        clauses.append(RawEvent.processed == processed)
    if event_type:
        # dialect-aware JSON extraction
        dialect_name = None
        try:
            dialect_name = db.bind.dialect.name  # type: ignore[attr-defined]
        except Exception:
            dialect_name = None
        if dialect_name == "postgresql":
            stmt = stmt.where(and_(*clauses)) if clauses else stmt
            stmt = stmt.where(text("(payload->> 'event_type') = :event_type")).params(event_type=event_type)
            clauses = []
        else:
            stmt = stmt.where(and_(*clauses)) if clauses else stmt
            stmt = stmt.where(func.json_extract(RawEvent.payload, "$.event_type") == event_type)
            clauses = []
    if clauses:
        stmt = stmt.where(and_(*clauses))
    # only Gmail source
    stmt = stmt.where(RawEvent.source == "gmail")
    stmt = stmt.order_by(RawEvent.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return {"status": "success", "data": [
        {
            "id": str(r.id),
            "tenant_id": str(r.tenant_id) if r.tenant_id else None,
            "processed": r.processed,
            "payload": r.payload,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows
    ]}


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
        norm_param = tenant_id.replace('-', '').lower()
        clauses.append(func.replace(_cast(NormalizedEvent.tenant_id, _String), '-', '') == norm_param)
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
    # Dialect-aware JSON extraction for idempotency_key inside details JSON
    dialect_name = None
    try:
        dialect_name = db.bind.dialect.name  # type: ignore[attr-defined]
    except Exception:
        dialect_name = None

    stmt = select(AuditLog)
    if dialect_name == "postgresql":
        stmt = stmt.where(text("details->> 'idempotency_key' = :idempotency_key")).params(idempotency_key=idempotency_key)
    else:
        stmt = stmt.where(func.json_extract(AuditLog.details, "$.idempotency_key") == idempotency_key)
    stmt = stmt.order_by(AuditLog.created_at.asc())
    result = await db.execute(stmt)
    rows = result.scalars().all()
    data = []
    for r in rows:
        data.append({
            "id": str(r.id),
            "tenant_id": str(r.tenant_id) if r.tenant_id else None,
            "flow_id": r.flow_id,
            "action": r.action,
            "details": r.details,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return {"status": "success", "data": data}
