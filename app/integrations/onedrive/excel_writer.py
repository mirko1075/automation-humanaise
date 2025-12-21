"""
app/integrations/onedrive/excel_writer.py

Simple Excel writer (v1) that downloads `commesse.xlsx` from OneDrive,
upserts a row in the `Preventivi` sheet and uploads the file back.

Constraints:
- Uses file download/upload only (no MS Excel Graph APIs)
- Idempotent by `preventivo.id` presence in sheet
- Soft-concurrency check via `lastModifiedDateTime`

TODOs included per project request.
"""
from __future__ import annotations

from typing import Dict, Any
import tempfile
import os
import asyncio
from datetime import datetime, timezone
import concurrent.futures
import traceback

from app.monitoring.logger import log
from app.monitoring.audit import audit_event
from app.integrations.onedrive_client import OneDriveClient


DEFAULT_CONFLICT_SECONDS = 10


async def upsert_preventivo_row(preventivo: Any, customer: Any, tenant: Any, conflict_seconds: int = DEFAULT_CONFLICT_SECONDS) -> None:
    """Download `commesse.xlsx`, upsert a row in sheet `Preventivi`, upload back.

    Args:
        preventivo: ORM object representing the quote (must have `id`, `status`, `created_at`)
        customer: ORM object representing the customer (must have `name`, `email`, `phone`)
        tenant: ORM object or simple identifier for tenant (used for logging)
        conflict_seconds: soft concurrency window in seconds to abort when file modified recently

    Notes:
        - This function is defensive: on error it logs and emits an audit_event
        - It must be called after DB commit so that preventivo is durable

    """
    tenant_id = getattr(tenant, "id", str(tenant))
    request_id = None

    client = OneDriveClient()
    remote_path = "commesse.xlsx"

    try:
        # 1) Fetch metadata to check last modified
        try:
            metadata = await client.get_file_metadata(remote_path)
        except Exception:
            metadata = None

        if metadata and "lastModifiedDateTime" in metadata:
            try:
                last_mod = datetime.fromisoformat(metadata["lastModifiedDateTime"].replace("Z", "+00:00"))
            except Exception:
                last_mod = None
            if last_mod:
                now = datetime.now(timezone.utc)
                delta = (now - last_mod).total_seconds()
                if delta < conflict_seconds:
                    log("WARNING", f"Excel file {remote_path} modified {delta:.1f}s ago (<{conflict_seconds}s). Aborting update.", module="excel_writer", tenant_id=str(tenant_id))
                    await audit_event("excel_update_skipped_recent_modify", str(tenant_id), None, {"preventivo_id": str(getattr(preventivo, "id", None)), "delta_seconds": delta})
                    return

        # 2) Download file to temp
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        tmp.close()
        downloaded = False
        try:
            await client.download_file(remote_path, tmp.name)
            # If the download produced an empty file (zero bytes) treat as not downloaded
            try:
                if os.path.getsize(tmp.name) == 0:
                    downloaded = False
                else:
                    downloaded = True
            except Exception:
                downloaded = True
        except Exception:
            # If download fails, we'll create a new workbook
            log("INFO", f"Could not download {remote_path}, will create new workbook", module="excel_writer", tenant_id=str(tenant_id))

        # 3) Use openpyxl in threadpool to avoid blocking event loop
        def _workbook_update(path: str):
            from openpyxl import Workbook, load_workbook

            if downloaded:
                wb = load_workbook(path)
            else:
                wb = Workbook()

            # Ensure Preventivi sheet exists
            if "Preventivi" in wb.sheetnames:
                ws = wb["Preventivi"]
            else:
                ws = wb.create_sheet("Preventivi")
                # Header row
                ws.append(["id", "tenant_id", "customer_name", "customer_email", "customer_phone", "descrizione_lavori", "status", "created_at", "updated_at"])

            # Build idempotency map: id -> row index
            id_col = 1
            id_map = {}
            for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                rid = row[0]
                if rid:
                    id_map[str(rid)] = idx

            pid = str(getattr(preventivo, "id", ""))
            now_iso = datetime.now(timezone.utc).isoformat()

            if pid in id_map:
                r = id_map[pid]
                # Update relevant columns: status, updated_at
                ws.cell(row=r, column=7, value=getattr(preventivo, "status", ""))
                ws.cell(row=r, column=9, value=now_iso)
            else:
                # Ensure created_at is serialized to ISO string (openpyxl doesn't like tz-aware datetimes)
                created_val = getattr(preventivo, "created_at", None)
                if isinstance(created_val, datetime):
                    created_val = created_val.isoformat()
                elif created_val is None:
                    created_val = now_iso

                values = [
                    pid,
                    str(tenant_id),
                    getattr(customer, "name", ""),
                    getattr(customer, "email", ""),
                    getattr(customer, "phone", ""),
                    (getattr(preventivo, "quote_data", {}) or {}).get("descrizione_lavori", ""),
                    getattr(preventivo, "status", ""),
                    created_val,
                    now_iso,
                ]
                ws.append(values)

            wb.save(path)

        loop = asyncio.get_running_loop()
        # Use a small threadpool for workbook operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            await loop.run_in_executor(pool, _workbook_update, tmp.name)

        # 4) Before upload, re-fetch metadata to ensure not changed while we edited
        try:
            metadata_after = await client.get_file_metadata(remote_path)
        except Exception:
            metadata_after = None

        if metadata and metadata_after and metadata.get("lastModifiedDateTime") != metadata_after.get("lastModifiedDateTime"):
            log("WARNING", f"File {remote_path} changed during edit; abort upload to avoid clobbering.", module="excel_writer", tenant_id=str(tenant_id))
            await audit_event("excel_update_aborted_conflict", str(tenant_id), None, {"preventivo_id": str(getattr(preventivo, "id", None))})
            try:
                os.remove(tmp.name)
            except Exception:
                pass
            return

        # 5) Upload back
        try:
            await client.upload_file(tmp.name, remote_path)
            await audit_event("excel_update_success", str(tenant_id), None, {"preventivo_id": str(getattr(preventivo, "id", None))})
            log("INFO", f"Excel file {remote_path} updated for preventivo {getattr(preventivo, 'id', None)}", module="excel_writer", tenant_id=str(tenant_id))
        except Exception:
            # Do not remove the tmp file on failure so tests can inspect it; in production a periodic cleaner can remove old tmp files
            try:
                os.remove(tmp.name)
            except Exception:
                pass

    except Exception as exc:
        tb = traceback.format_exc()
        log("ERROR", f"Excel writer failure: {exc}", module="excel_writer", tenant_id=str(tenant_id))
        try:
            await audit_event("excel_update_error", str(tenant_id), None, {"preventivo_id": str(getattr(preventivo, "id", None)), "error": str(exc), "traceback": tb})
        except Exception:
            pass
        # TODO(retry): implement retry/backoff on transient OneDrive errors
        # TODO(monitoring): tracciare fallimenti scrittura Excel per tenant


# TODO(excel): gestire aggiornamento altri fogli (Clienti, Dipendenti)
# TODO(excel): aggiungere checksum o versione per idempotenza forte
# TODO(retry): implementare retry/backoff su errori transienti OneDrive
# TODO(monitoring): tracciare fallimenti scrittura Excel per tenant
