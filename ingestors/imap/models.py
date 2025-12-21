"""
ingestors/imap/models.py

Data models for IMAP ingestor. These are lightweight dataclasses used
to pass data between components and to construct the Normalizer `InboundMessage`.
"""
from dataclasses import dataclass
from typing import List, Optional
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
    uid: int
    uidvalidity: str
    message_id: Optional[str]
    subject: Optional[str]
    from_: Optional[str]
    to: Optional[List[str]]
    date: Optional[datetime]
    text: Optional[str]
    html: Optional[str]
    attachments: List[Attachment]
