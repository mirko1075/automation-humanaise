"""
ingestors/imap/parser.py

Parse raw RFC822 messages into `RawEmail` model, extracting text, html and attachments.
"""
from __future__ import annotations

import email
from email.policy import default
from typing import Tuple, List, Optional
from datetime import datetime
import logging
import os
if not logging.getLogger().hasHandlers():
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
from .models import RawEmail, Attachment
logger = logging.getLogger(__name__)


def parse_rfc822(raw_bytes: bytes, tenant_id: str, mailbox: str, uid: int, uidvalidity: str) -> RawEmail:
    """Parse raw message bytes into RawEmail dataclass.

    Prefers text/plain for `text`; `html` set if text/html present.
    Attachments are returned as list of `Attachment`.
    """
    logger.debug("Parsing RFC822 message", extra={"tenant_id": tenant_id, "mailbox": mailbox, "uid": uid, "uidvalidity": uidvalidity})
    msg = email.message_from_bytes(raw_bytes, policy=default)

    subject = msg.get('Subject')
    from_ = msg.get('From')
    to = msg.get_all('To', [])
    message_id = msg.get('Message-ID')
    date_hdr = msg.get('Date')
    parsed_date = None
    try:
        if date_hdr:
            parsed_date = email.utils.parsedate_to_datetime(date_hdr)
    except Exception:
        logger.debug("failed_parse_date", date_hdr=date_hdr)

    text_parts: List[str] = []
    html_parts: List[str] = []
    attachments: List[Attachment] = []

    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = part.get_content_disposition()
            if disp == 'attachment' or part.get_filename():
                filename = part.get_filename() or 'attachment'
                payload = part.get_payload(decode=True) or b''
                attachments.append(Attachment(filename=filename, content_type=ctype, data=payload))
            elif ctype == 'text/plain' and disp != 'attachment':
                payload = part.get_content()
                if isinstance(payload, str):
                    text_parts.append(payload)
            elif ctype == 'text/html' and disp != 'attachment':
                payload = part.get_content()
                if isinstance(payload, str):
                    html_parts.append(payload)
    else:
        ctype = msg.get_content_type()
        if ctype == 'text/plain':
            text_parts.append(msg.get_content())
        elif ctype == 'text/html':
            html_parts.append(msg.get_content())

    text = '\n'.join(text_parts).strip() if text_parts else None
    html = '\n'.join(html_parts).strip() if html_parts else None

    return RawEmail(
        tenant_id=tenant_id,
        mailbox=mailbox,
        uid=uid,
        uidvalidity=uidvalidity,
        message_id=message_id,
        subject=subject,
        from_=from_,
        to=to,
        date=parsed_date,
        text=text,
        html=html,
        attachments=attachments,
    )
