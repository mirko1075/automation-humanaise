# ingestors/imap/adapter.py
"""
Adapter to convert RawEmail (internal dataclass) into the Normalizer's InboundMessage shape
as specified in Appendix A. This is a pure mapping function with no external side-effects
and leaves attachment storage_url as None (upload/deferred by other systems).
"""
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.monitoring.logger import structlog

from ingestors.imap.models import RawEmail, Attachment

logger = structlog.get_logger()


def rawemail_to_inbound(raw: RawEmail) -> Dict[str, Any]:
    """
    Map a RawEmail to the InboundMessage dict required by the normalizer contract (Appendix A).

    Args:
        raw: RawEmail instance produced by the IMAP parser

    Returns:
        A dict matching the InboundMessage JSON schema. Attachment `storage_url` is set to None.
    """

    # Source information: account_id should be the tenant/account used for IMAP connection
    source = {
        "provider": "imap",
        "account_id": raw.tenant_id,
        "mailbox": raw.mailbox,
        "message_uid": raw.uid,
        "uidvalidity": raw.uidvalidity,
    }

    # Simplify header mappings
    headers = {k: v for k, v in raw.headers.items()} if getattr(raw, "headers", None) else {}

    # Build attachments list per Appendix A
    attachments: List[Dict[str, Any]] = []
    for a in raw.attachments:
        att: Dict[str, Any] = {
            "filename": a.filename,
            "content_type": a.content_type,
            "size": len(a.data) if a.data is not None else None,
            "storage_url": None,
        }
        attachments.append(att)

    inbound: Dict[str, Any] = {
        "id": raw.event_id,
        "received_at": raw.received_at.isoformat() if isinstance(raw.received_at, datetime) else raw.received_at,
        "source": source,
        "message_id": raw.message_id,
        "subject": raw.subject,
        "from": raw.from_,
        "to": raw.to,
        "cc": raw.cc,
        "bcc": raw.bcc,
        "text": raw.text,
        "html": raw.html,
        "headers": headers,
        "attachments": attachments,
        "raw_payload": None,
    }

    logger.debug("mapped_rawemail_to_inbound", event_id=raw.event_id, tenant_id=raw.tenant_id)
    return inbound
