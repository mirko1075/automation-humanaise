"""
ingestors/imap/models.py

Data models for IMAP ingestor. These are lightweight dataclasses used
to pass data between components and to construct the Normalizer `InboundMessage`.
"""
from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime


@dataclass
class Attachment:
    filename: str
    content_type: str
    data: bytes


@dataclass
class RawEmail:
    tenant_id: str
    mailbox: str
    uid: int | str
    uidvalidity: str

    message_id: str
    subject: Optional[str]
    from_: Optional[str]
    to: List[str]

    date: Optional[datetime]
    text: Optional[str]
    html: Optional[str]

    attachments: list

    # Structural optional fields used by adapter (should be provided by providers)
    event_id: Optional[str] = None
    received_at: Optional[datetime] = None
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    headers: Optional[Dict[str, str]] = None
    raw_payload: Optional[dict] = None
