import datetime

from ingestors.imap.models import RawEmail, Attachment
from ingestors.imap.adapter import rawemail_to_inbound


def make_raw_email(with_attachment: bool = True) -> RawEmail:
    dt = datetime.datetime(2025, 12, 27, 12, 0, 0)
    attachments = []
    if with_attachment:
        attachments = [Attachment(filename="file.pdf", content_type="application/pdf", data=b"PDFDATA123")]

    raw = RawEmail(
        tenant_id="tenant_123",
        mailbox="INBOX",
        uid=42,
        uidvalidity="uidv-1",
        message_id="<msg-1@example.com>",
        subject="Hello",
        from_="sender@example.com",
        to=["recipient@example.com"],
        date=dt,
        text="Plain text body",
        html=None,
        attachments=attachments,
    )

    # Adapter expects some additional attributes; tests set them here.
    raw.event_id = "evt-42"
    raw.received_at = dt
    raw.headers = {"X-Test": "1"}
    raw.cc = []
    raw.bcc = []

    return raw


def test_rawemail_to_inbound_with_attachment():
    raw = make_raw_email(with_attachment=True)
    inbound = rawemail_to_inbound(raw)

    assert inbound["id"] == "evt-42"
    assert inbound["source"]["provider"] == "imap"
    assert inbound["source"]["account_id"] == "tenant_123"
    assert inbound["message_id"] == "<msg-1@example.com>"
    assert inbound["subject"] == "Hello"
    assert inbound["text"] == "Plain text body"
    assert isinstance(inbound["attachments"], list)
    assert len(inbound["attachments"]) == 1
    att = inbound["attachments"][0]
    assert att["filename"] == "file.pdf"
    assert att["content_type"] == "application/pdf"
    assert att["size"] == len(b"PDFDATA123")
    assert att["storage_url"] is None


def test_rawemail_to_inbound_no_attachments():
    raw = make_raw_email(with_attachment=False)
    inbound = rawemail_to_inbound(raw)

    assert inbound["attachments"] == []
    assert inbound["raw_payload"] is None
