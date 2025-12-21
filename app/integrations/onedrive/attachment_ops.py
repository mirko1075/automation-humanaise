"""
app/integrations/onedrive/attachment_ops.py

Helpers to save attachments for a follow-up into a deterministic OneDrive
folder tree under the configured ONEDRIVE_BASE_PATH.

Responsibilities:
- Build deterministic folder path: Preventivi/Clienti/<customerId> - <RagioneSociale>/<PROTOCOLLO>/Allegati/
- Ensure uploaded filenames follow: YYYY-MM-DD_HHMM_<messageId|historyId>_<original_filename>
- Avoid overwriting by checking existence and appending a numeric suffix when needed
- Emit audit events and human-friendly console logs for each saved attachment
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import tempfile
import os
from datetime import datetime
import traceback

from app.integrations.onedrive_client import OneDriveClient
from app.monitoring.logger import log as app_log, console_info
from app.monitoring.audit import audit_event


async def save_attachments_for_followup(
    preventivo: Any,
    customer: Any,
    attachments: Optional[List[Dict[str, Any]]],
    tenant_id: Any,
    protocollo: str,
) -> List[Dict[str, Any]]:
    """Save attachments to OneDrive for a follow-up event.

    Args:
        preventivo: ORM object for the linked preventivo (must have `id`)
        customer: ORM object for the customer (must have `id` and `name`)
        attachments: list of attachment metadata dicts. Supported keys:
            - `filename`: original filename (required)
            - `local_path`: path to a local file to upload (preferred)
            - `content_bytes`: bytes of the file (will be written to temp file)
            - `messageId` or `historyId`: used in naming
        tenant_id: tenant identifier (used for logging/audit)
        protocollo: extracted protocol string used to build folder name

    Returns:
        A list of dicts with saved attachment metadata (remote_path, filename, status).
    """
    results: List[Dict[str, Any]] = []
    if not attachments:
        return results

    client = OneDriveClient()

    tenant_str = getattr(tenant_id, "id", str(tenant_id))
    customer_id = getattr(customer, "id", None)
    customer_name = getattr(customer, "name", "") or ""

    # Build deterministic remote directory path
    # e.g. Preventivi/Clienti/<customerId> - <RagioneSociale>/<PROTOCOLLO>/Allegati
    safe_cname = customer_name.replace('/', '_') if customer_name else ""
    remote_dir = f"Preventivi/Clienti/{customer_id} - {safe_cname}/{protocollo}/Allegati"

    try:
        await audit_event("followup.onedrive.ensure_folders.start", str(tenant_str), None, {"preventivo_id": str(getattr(preventivo, "id", None)), "remote_dir": remote_dir})
    except Exception:
        pass
    try:
        console_info(f"Ensuring OneDrive folder: {remote_dir}")
    except Exception:
        pass

    # Note: OneDriveClient does not provide a direct "ensure path" API here;
    # we rely on uploading files by path which will create folders as needed
    # in many OneDrive setups. We still log the intent and proceed.

    for att in attachments:
        try:
            orig_name = att.get("filename") or att.get("name")
            if not orig_name:
                results.append({"status": "skipped", "reason": "no_filename", "attachment": att})
                continue

            # Determine local path: prefer provided local_path, else write content_bytes
            local_path = att.get("local_path")
            if not local_path and att.get("content_bytes"):
                tmp = tempfile.NamedTemporaryFile(delete=False)
                try:
                    tmp.write(att.get("content_bytes"))
                    tmp.flush()
                finally:
                    tmp.close()
                local_path = tmp.name

            if not local_path or not os.path.exists(local_path):
                results.append({"status": "skipped", "reason": "no_local_content", "filename": orig_name})
                continue

            # Build base filename
            ts = datetime.utcnow().strftime("%Y-%m-%d_%H%M")
            mid = att.get("messageId") or att.get("historyId") or att.get("id") or "msg"
            base_fname = f"{ts}_{mid}_{orig_name}"

            # Ensure uniqueness by checking metadata existence
            remote_path = f"{remote_dir}/{base_fname}"
            suffix = 0
            while True:
                try:
                    await client.get_file_metadata(remote_path)
                    # exists -> increment suffix
                    suffix += 1
                    remote_path = f"{remote_dir}/{base_fname}_{suffix}"
                except Exception:
                    # not found or other error -> proceed to upload
                    break

            # Upload
            try:
                await audit_event("followup.attachments.save.start", str(tenant_str), None, {"preventivo_id": str(getattr(preventivo, "id", None)), "remote_path": remote_path, "filename": orig_name})
            except Exception:
                pass

            try:
                await client.upload_file(local_path, remote_path)
                try:
                    await audit_event("followup.attachments.save.done", str(tenant_str), None, {"preventivo_id": str(getattr(preventivo, "id", None)), "remote_path": remote_path, "filename": orig_name})
                except Exception:
                    pass
                try:
                    console_info(f"Saved attachment to OneDrive: {remote_path}")
                except Exception:
                    pass
                results.append({"status": "saved", "remote_path": remote_path, "filename": orig_name})
            except Exception as exc:
                tb = traceback.format_exc()
                app_log("ERROR", f"Failed uploading attachment {orig_name}: {exc}", module="attachment_ops", tenant_id=str(tenant_str), preventivo_id=str(getattr(preventivo, "id", None)))
                try:
                    await audit_event("followup.attachments.save.error", str(tenant_str), None, {"preventivo_id": str(getattr(preventivo, "id", None)), "filename": orig_name, "error": str(exc), "traceback": tb})
                except Exception:
                    pass
                results.append({"status": "error", "reason": str(exc), "filename": orig_name})
            finally:
                # If we wrote a temp file for content_bytes, remove it
                if att.get("content_bytes") and local_path and os.path.exists(local_path):
                    try:
                        os.remove(local_path)
                    except Exception:
                        pass

    try:
        await audit_event("followup.onedrive.ensure_folders.done", str(tenant_str), None, {"preventivo_id": str(getattr(preventivo, "id", None)), "remote_dir": remote_dir, "saved_count": sum(1 for r in results if r.get("status") == "saved")})
    except Exception:
        pass

    return results
