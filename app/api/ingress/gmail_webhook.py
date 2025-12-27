# --- Module-level sync audit write utility ---
def _sync_audit_write(a_action, a_tenant, a_payload, flow_id=""):
    try:
        sync_url = str(_settings.DATABASE_URL or "sqlite:///./.audit_fallback.db")
        sync_url = sync_url.replace("+asyncpg", "")
        sync_url = sync_url.replace("+aiosqlite", "")
        eng = _create_engine(sync_url)
        Session = _sessionmaker(bind=eng)
        s = Session()
        try:
            al = _AuditLog(
                id=_uuid4(),
                tenant_id=a_tenant,
                flow_id=flow_id,
                action=a_action,
                actor=None,
                details=a_payload,
                created_at=_dt.utcnow(),
                updated_at=_dt.utcnow(),
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
        pass
# app/api/ingress/gmail_webhook.py
"""
Gmail Pub/Sub webhook endpoint for Edilcos Automation Backend.

ARCHITECTURAL NOTE (important):
 - This webhook strictly acts as an ingest-only endpoint.
 - It MUST NOT call Gmail APIs or attempt to fetch message bodies.
 - It decodes the Pub/Sub `message.data` (base64), extracts `historyId` and
     `emailAddress`, persists a `RawEvent` referencing these values, and
     returns HTTP 200 immediately to ACK the Pub/Sub push.
 - All Gmail API interactions (e.g. `users.history.list`, message fetches)
     are performed later by the normalizer/worker pipeline.

Rationale: fast ACK, resilience, and correct retry semantics.
"""
# TODO(monitoring): expose counter for raw_events_received_total{tenant,flow,outcome}
# TODO(alerting): alert if RawEvent persistence fails repeatedly for a tenant
# TODO(replay): store raw payload to durable object storage if persistence permanently fails
from fastapi import APIRouter, Request, BackgroundTasks, Depends
import time
from fastapi.responses import JSONResponse
from app.monitoring.logger import log
from app.monitoring.logger import console_info, log_human
from app.monitoring.audit import audit_event
from app.monitoring.slack_alerts import send_slack_alert
from app.db.repositories.raw_event_repository import RawEventRepository
from app.db.repositories.tenant_repository import TenantRepository
from app.db.session import SessionLocal
import asyncio
from uuid import UUID
import base64
import json
import traceback
from fastapi import Depends
from app.db.session import get_async_session, SessionLocal
from sqlalchemy.exc import IntegrityError
from app.config import settings as _settings
from sqlalchemy import create_engine as _create_engine, text as _text
from sqlalchemy.orm import sessionmaker as _sessionmaker
from app.config import settings as _settings
from app.db.models import AuditLog as _AuditLog
from uuid import uuid4 as _uuid4
from datetime import datetime as _dt

router = APIRouter(prefix="/gmail", tags=["gmail"])

async def get_tenant_id(email_address: str, db):
    """Find tenant by email address using a fresh synchronous DB connection.

    We run this lookup in a thread using a fresh sync engine to avoid
    reusing the application's async engine/session and prevent any
    cross-event-loop Future attachment issues.
    """
    from app.config import settings as _settings
    from sqlalchemy import create_engine as _create_engine, text as _text
    from sqlalchemy.orm import sessionmaker as _sessionmaker

    def _sync_lookup(email_addr: str) -> str | None:
        try:
            sync_url = str(_settings.DATABASE_URL or "sqlite:///./.tenant_lookup.db")
            sync_url = sync_url.replace("+asyncpg", "")
            sync_url = sync_url.replace("+aiosqlite", "")
            eng = _create_engine(sync_url)
            Session = _sessionmaker(bind=eng)
            s = Session()
            try:
                # 1) check ExternalToken mapping
                row = s.execute(_text("SELECT tenant_id FROM external_tokens WHERE external_id = :email LIMIT 1"), {"email": email_addr}).first()
                if row and row[0]:
                    return str(row[0])

                # 2) check Tenant by contact_channels JSON (email list)
                # contact_channels -> JSON like {"email": ["a@b.com"], "whatsapp": ["+39..."]}
                row = s.execute(_text("SELECT id, contact_channels FROM tenants WHERE contact_channels IS NOT NULL")).fetchall()
                for r in row:
                    try:
                        tid = r[0]
                        channels = r[1] or {}
                        emails = channels.get('email') if isinstance(channels, dict) else None
                        if emails and isinstance(emails, list):
                            if email_addr.lower() in [e.lower() for e in emails if isinstance(e, str)]:
                                return str(tid)
                    except Exception:
                        continue

                return None
            finally:
                s.close()
                try:
                    eng.dispose()
                except Exception:
                    pass
        except Exception:
            return None

    import asyncio
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_lookup, email_address)

@router.post("/webhook")
async def gmail_webhook(request: Request, background_tasks: BackgroundTasks):
    request_id = getattr(request.state, "request_id", None)
    # Flow-level start timestamp for end-to-end timing
    flow_start = time.monotonic()
    # Persist flow_start for downstream correlation
    try:
        request.state.flow_start = flow_start
    except Exception:
        pass

    log("INFO", "webhook.received.start", module="gmail_webhook", request_id=str(request_id) if request_id is not None else None)
    # Human-friendly console line
    console_info("Webhook received")
    # Short human log for operators
    log_human("Webhook received")
    # Persist timeline entry for admin UI
    try:
        await audit_event("webhook.received.start", None, None, {"request_id": str(request_id) if request_id is not None else None, "note": "ingress start"})
    except Exception:
        # best-effort: do not fail ingest if audit write fails
        pass
    log("INFO", "GMAIL WEBHOOK HIT", raw_body=request.body)

    try:
        body = await request.json()
        # Expect Pub/Sub push envelope as documented by Google
        # {
        #   "message": { "data": "<BASE64>", "attributes": {...}, "messageId": "...", "publishTime": "..." },
        #   "subscription": "..."
        # }
        envelope = body.get("message") if isinstance(body, dict) else None
        if not envelope:
            log("WARNING", "Invalid Pub/Sub envelope: missing 'message'", module="gmail_webhook", request_id=str(request_id))
            return JSONResponse(status_code=400, content={"error": "Invalid envelope", "request_id": request_id})
        data_b64 = envelope.get("data")
        log("DEBUG", "DATA B64 present", module="gmail_webhook", data_present=bool(data_b64))
        if not data_b64:
            log("WARNING", "Missing data in Pub/Sub envelope", module="gmail_webhook", request_id=str(request_id))
            return JSONResponse(status_code=400, content={"error": "Missing data", "request_id": request_id})
        # WEBHOOK PARSE START
        parse_start = time.monotonic()
        log("INFO", "webhook.parse.start", module="gmail_webhook", request_id=str(request_id) if request_id is not None else None)
        console_info("Parsing Gmail payload")
        log_human("Parsing Gmail payload")
        try:
            await audit_event("webhook.parse.start", None, None, {"request_id": str(request_id) if request_id is not None else None})
        except Exception:
            pass

        decoded = base64.urlsafe_b64decode(data_b64 + "==")
        payload = None
        # Try to parse JSON from the decoded bytes using multiple fallbacks
        try:
            payload = json.loads(decoded)
        except Exception:
            try:
                # Decode as UTF-8, replacing invalid chars, then parse
                text = decoded.decode("utf-8", errors="replace")
                payload = json.loads(text)
            except Exception:
                try:
                    # Try latin-1 as a fallback
                    text = decoded.decode("latin-1", errors="replace")
                    payload = json.loads(text)
                except Exception:
                    try:
                        # Attempt to extract a JSON object substring between braces
                        text = decoded.decode("utf-8", errors="ignore")
                        start = text.find("{")
                        end = text.rfind("}")
                        if start != -1 and end != -1 and end > start:
                            payload = json.loads(text[start:end+1])
                        else:
                            raise ValueError("no-json-substring")
                    except Exception:
                        # Last resort: keep raw base64 payload so we don't lose the event
                        payload = {"_raw_base64": data_b64}
                        try:
                            log("WARNING", "Gmail webhook payload could not be JSON-decoded; stored raw base64", module="gmail_webhook", request_id=str(request_id))
                        except Exception:
                            pass
        # WEBHOOK PARSE DONE
        try:
            parse_duration_ms = int((time.monotonic() - parse_start) * 1000)
            log("INFO", "webhook.parse.done", module="gmail_webhook", request_id=str(request_id) if request_id is not None else None, duration_ms=parse_duration_ms)
            console_info("Gmail payload parsed")
            log_human("Gmail payload parsed")
            try:
                await audit_event("webhook.parse.done", None, None, {"duration_ms": parse_duration_ms, "request_id": str(request_id) if request_id is not None else None})
            except Exception:
                pass
        except Exception:
            pass
        # Gmail Pub/Sub payload contains a reference, not full message content
        history_id = payload.get("historyId")
        email_address = payload.get("emailAddress")
        # messageId may not be present in the Pub/Sub payload; Gmail delivers historyId
        message_id = payload.get("messageId") or envelope.get("messageId") or envelope.get("attributes", {}).get("messageId")
        # Only historyId and emailAddress are required for the pipeline
        missing_fields = [f for f in ["historyId", "emailAddress"] if not payload.get(f)]
        if missing_fields:
            log("WARNING", f"Missing fields: {missing_fields}", module="gmail_webhook", request_id=str(request_id) if request_id is not None else "")
        import sys
        test_mode = "pytest" in sys.modules


        if not isinstance(email_address, str) or not email_address:
            log("ERROR", f"Invalid or missing email_address: {email_address}", module="gmail_webhook", request_id=str(request_id) if request_id is not None else "")
            tenant_id = None
        else:
            tenant_id = await get_tenant_id(email_address, None)

        # Persist as RawEvent (canonical ingress/audit log)
        # Use a synchronous DB write executed in a threadpool to avoid asyncpg
        # connection-concurrency issues in the request event loop. This keeps
        # the webhook ingest fast and isolated from the async DB pool.
        idempotency_key = message_id or history_id or None
        canonical_payload = payload or {"_raw_base64": data_b64}
        outcome = "received" if tenant_id else "unassigned"

        def _sync_create_rawevent(a_tenant_id, a_flow_id, a_source, a_payload, a_idempotency_key):
            """Create RawEvent synchronously using a fresh sync engine/session.

            Returns the created event id on success. Raises the original
            exception to the caller so we can handle IntegrityError (idempotency)
            and other errors appropriately.
            """
            from app.config import settings as _settings_local
            from sqlalchemy import create_engine as _create_engine, text as _text
            from sqlalchemy.orm import sessionmaker as _sessionmaker
            from app.db.models import RawEvent as _RawEvent
            from uuid import uuid4 as _uuid4_local
            from datetime import datetime as _dt_local

            sync_url = str(_settings_local.DATABASE_URL or "sqlite:///./.rawevent_sync.db")
            sync_url = sync_url.replace("+asyncpg", "")
            sync_url = sync_url.replace("+aiosqlite", "")
            eng = _create_engine(sync_url)
            Session = _sessionmaker(bind=eng)
            s = Session()
            try:
                ev = _RawEvent(
                    id=_uuid4_local(),
                    tenant_id=a_tenant_id,
                    flow_id=a_flow_id,
                    source=a_source,
                    payload=a_payload,
                    processed=False,
                    idempotency_key=a_idempotency_key or "",
                    created_at=_dt_local.utcnow(),
                    updated_at=_dt_local.utcnow(),
                    deleted_at=None,
                )
                s.add(ev)
                s.commit()
                s.refresh(ev)
                return str(ev.id)
            finally:
                try:
                    s.close()
                except Exception:
                    pass
                try:
                    eng.dispose()
                except Exception:
                    pass

        try:
            loop = asyncio.get_running_loop()
            # execute sync DB insert in threadpool
            ev_id = await loop.run_in_executor(
                None,
                _sync_create_rawevent,
                tenant_id,
                None,
                "gmail",
                {
                    "channel": "email",
                    "identifier": email_address,
                    "external_ref": str(history_id) if history_id is not None else None,
                    "outcome": outcome,
                    "original": canonical_payload,
                },
                str(idempotency_key) if idempotency_key is not None else "",
            )
        except Exception as exc:
            # Handle IntegrityError (unique idempotency) specially if it originates
            # from the DB layer. Since we're in a thread, we need to inspect the
            # exception chain for IntegrityError from SQLAlchemy/DBAPI.
            import sqlalchemy
            from sqlalchemy.exc import IntegrityError as _IntegrityError
            tb = traceback.format_exc()
            # If it's an IntegrityError, treat as duplicate -> ACK
            if isinstance(exc, _IntegrityError) or any(isinstance(e, _IntegrityError) for e in getattr(exc, "__cause__", []) or []):
                try:
                    log("INFO", f"Duplicate RawEvent idempotency_key={idempotency_key}", module="gmail_webhook", request_id=str(request_id) if request_id is not None else "")
                    # Audit duplicate as skipped
                    try:
                        await audit_event("webhook.received.skipped", None, None, {"idempotency_key": str(idempotency_key) if idempotency_key else None, "request_id": str(request_id) if request_id is not None else None})
                    except Exception:
                        pass
                except Exception:
                    pass
                return JSONResponse(content={"status": "received", "request_id": str(request_id) if request_id is not None else ""})

            log("ERROR", f"Exception persisting RawEvent: {exc}\n{tb}", module="gmail_webhook", request_id=str(request_id) if request_id is not None else "")
            try:
                loop.run_in_executor(None, _sync_audit_write, "gmail_ingress_exception", None, {"error": str(exc), "traceback": tb}, "gmail_ingress_exception")
            except Exception:
                pass
            return JSONResponse(status_code=500, content={"error": "Internal Server Error", "request_id": str(request_id) if request_id is not None else ""})

        log("INFO", f"RawEvent persisted id={ev_id} tenant_id={tenant_id}", module="gmail_webhook", request_id=str(request_id) if request_id is not None else "", tenant_id=tenant_id)
        console_info("RawEvent saved")
        log_human("RawEvent saved")
        # WEBHOOK RECEIVED DONE
        try:
            webhook_duration_ms = int((time.monotonic() - flow_start) * 1000)
            log("INFO", "webhook.received.done", module="gmail_webhook", request_id=str(request_id) if request_id is not None else None, raw_event_id=ev_id, tenant_id=tenant_id, duration_ms=webhook_duration_ms)
            try:
                await audit_event("webhook.received.done", tenant_id, None, {"raw_event_id": str(ev_id), "duration_ms": webhook_duration_ms, "outcome": outcome})
            except Exception:
                pass
        except Exception:
            pass

        return JSONResponse(content={"status": outcome, "request_id": str(request_id) if request_id is not None else ""})
        # Idempotency check: perform using a fresh sync connection in a
        # thread to avoid using the request's AsyncSession which may be
        # impacted by event-loop/greenlet issues during test runs.

        def _sync_idempotency_check(a_tenant_id, a_message_id) -> bool:
            try:
                sync_url = str(_settings.DATABASE_URL or "sqlite:///./.idempotency_check.db")
                sync_url = sync_url.replace("+asyncpg", "")
                sync_url = sync_url.replace("+aiosqlite", "")
                eng = _create_engine(sync_url)
                Session = _sessionmaker(bind=eng)
                s = Session()
                try:
                    row = s.execute(_text("SELECT 1 FROM raw_events WHERE tenant_id = :tid AND idempotency_key = :mid LIMIT 1"), {"tid": str(a_tenant_id), "mid": a_message_id}).first()
                    return bool(row)
                finally:
                    s.close()
                    try:
                        eng.dispose()
                    except Exception:
                        pass
            except Exception:
                return False

        loop = asyncio.get_running_loop()
        # Use historyId as fallback idempotency key if message_id is missing
        idempotency_key = message_id or history_id
        is_dup = await loop.run_in_executor(None, _sync_idempotency_check, tenant_id, idempotency_key)
        if is_dup:
            log("INFO", f"Duplicate event for idempotency_key {idempotency_key}", module="gmail_webhook", request_id=str(request_id) if request_id is not None else "")
            return JSONResponse(content={"status": "received", "request_id": str(request_id) if request_id is not None else ""})

        # Do NOT call Gmail APIs here. Persist the reference (historyId/email)
        # so the normalizer/worker pipeline can perform history.list and fetch messages.
        enriched_payload = {**payload, "note": "referenced_event_only"}

        # Convert tenant_id to UUID if needed
        from uuid import UUID as _UUID
        try:
            tenant_uuid = tenant_id if isinstance(tenant_id, _UUID) else _UUID(str(tenant_id))
        except Exception:
            log("ERROR", f"Invalid tenant_id format: {tenant_id}", module="gmail_webhook", request_id=str(request_id) if request_id is not None else "")
            return JSONResponse(status_code=400, content={"error": "Invalid tenant_id format", "request_id": str(request_id) if request_id is not None else ""})

        
    except Exception as exc:
        tb = traceback.format_exc()
        log("ERROR", f"Exception in Gmail webhook: {exc}\n{tb}", module="gmail_webhook", request_id=str(request_id) if request_id is not None else "")
        # Schedule audit & slack notifications as background tasks to avoid
        # creating futures attached to a different event loop during error handling.
        # In exception handlers we must avoid creating or awaiting tasks
        # that may attach Futures to a different event loop. Instead,
        # schedule a synchronous fallback audit write in the threadpool
        # using a fresh sync engine. Do not call async alerting here.
        try:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, _sync_audit_write, "gmail_ingress_exception", None, {"error": str(exc), "traceback": tb}, "gmail_ingress_exception")
        except Exception as e:
            log("WARNING", f"Could not schedule sync fallback audit write: {e}", module="gmail_webhook", request_id=str(request_id) if request_id is not None else "")

        return JSONResponse(status_code=500, content={"error": "Internal Server Error", "request_id": str(request_id) if request_id is not None else ""})
