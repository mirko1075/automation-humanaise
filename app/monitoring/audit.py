# app/monitoring/audit.py
"""
Audit logging for Edilcos Automation Backend.
"""
from app.db.models import AuditLog
from app.db.session import SessionLocal
from datetime import datetime
from uuid import uuid4
from typing import Any, Dict, Optional
from app.monitoring.logger import log


async def audit_event(action: str, tenant_id: Optional[str], flow_id: Optional[str], payload: Dict[str, Any], actor: Optional[str] = None, request_id: Optional[str] = None):
    """Persist an audit log entry in a fail-safe way.

    This function always opens and manages its own DB session; it does
    NOT accept or reuse sessions from callers. It's safe to call from
    exception handlers and will never raise. On error it logs locally
    and attempts a synchronous fallback executed in a thread using a
    fresh sync engine derived from the configured DATABASE_URL.
    """
    try:
        # Always create our own async session so we never reuse a caller's session
        async with SessionLocal() as session:
            audit_log = AuditLog(
                id=uuid4(),
                tenant_id=tenant_id,
                flow_id=flow_id,
                action=action,
                actor=actor,
                details=payload,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(audit_log)
            await session.commit()
            return
    except Exception as e:
        # Log the primary failure but don't raise
        log("ERROR", f"Failed to write audit_event {action}: {e}", component="audit", request_id=request_id, tenant_id=tenant_id, flow_id=flow_id)

    # If we reach here, the async write failed. Use a synchronous
    # fallback in a background thread with a fresh sync engine to avoid
    # sharing the async engine or sessions with the caller.
    try:
        import asyncio as _asyncio
        from app.config import settings as _settings
        from sqlalchemy import create_engine as _create_engine
        from sqlalchemy.orm import sessionmaker as _sessionmaker

        def _sync_write(a_action, a_tenant_id, a_flow_id, a_payload, a_actor):
            try:
                sync_url = str(_settings.DATABASE_URL or "sqlite:///./.audit_fallback.db")
                sync_url = sync_url.replace("+asyncpg", "")
                sync_url = sync_url.replace("+aiosqlite", "")
                eng = _create_engine(sync_url)
                Session = _sessionmaker(bind=eng)
                s = Session()
                try:
                    al = AuditLog(
                        id=uuid4(),
                        tenant_id=a_tenant_id,
                        flow_id=a_flow_id,
                        action=a_action,
                        actor=a_actor,
                        details=a_payload,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                    s.add(al)
                    s.commit()
                finally:
                    s.close()
                    try:
                        eng.dispose()
                    except Exception:
                        pass
            except Exception:
                # Swallow errors in fallback: audit should never crash caller
                return

        loop = _asyncio.get_running_loop()
        # Schedule the sync write in the default threadpool executor
        loop.run_in_executor(None, _sync_write, action, tenant_id, flow_id, payload, actor)
    except Exception as e2:
        log("ERROR", f"Sync-thread fallback for audit_event failed: {e2}", component="audit", request_id=request_id, tenant_id=tenant_id, flow_id=flow_id)
