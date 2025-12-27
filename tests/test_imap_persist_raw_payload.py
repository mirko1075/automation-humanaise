"""
tests/test_imap_persist_raw_payload.py

Unit tests for IMAPRepository.persist_raw_message ensuring `raw_payload`
is stored when JSON-serializable and stored as NULL when not serializable.
"""
from dataclasses import dataclass
from typing import Any, Dict
import json

from ingestors.imap.repository import IMAPRepository
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


@dataclass
class FakeRawEmail:
    raw_bytes: bytes | None = None
    text: str | None = None
    mailbox: str | None = None
    uid: int | None = None
    uidvalidity: str | None = None
    raw_payload: Any | None = None


def _get_row_raw_payload(engine, row_id: int):
    # Helper to fetch the stored raw_payload column by id
    with Session(engine) as session:
        res = session.execute("SELECT raw_payload FROM imap_raw_events WHERE id = :id", {"id": row_id}).first()
        return res[0] if res else None


def test_persist_raw_payload_serializable(tmp_path):
    db_url = "sqlite:///:memory:"
    repo = IMAPRepository(db_url)

    payload = {"foo": "bar", "n": 1}
    raw = FakeRawEmail(raw_bytes=b"ok", mailbox="INBOX", uid=1, uidvalidity="v1", raw_payload=payload)
    metadata: Dict[str, Any] = {"message_id": "msg-1"}

    row_id = repo.persist_raw_message("tenant-a", raw, metadata)

    # persist_raw_message returns None; we need to query the DB to find the row
    # The repository uses autoincrement ids starting at 1; fetch the first row raw_payload
    engine = repo.engine
    with Session(engine) as session:
        res = session.execute(text("SELECT id, raw_payload FROM imap_raw_events WHERE message_id = :mid"), {"mid": "msg-1"}).first()
        assert res is not None
        stored = res[1]
        # Depending on DB/SQLAlchemy, JSON may be returned as native Python object
        # or as a JSON string (SQLite). Accept both forms.
        if isinstance(stored, str):
            parsed = json.loads(stored)
            assert parsed == payload
        else:
            assert stored == payload


def test_persist_raw_payload_not_serializable(tmp_path):
    db_url = "sqlite:///:memory:"
    repo = IMAPRepository(db_url)

    # Create a non-serializable payload (contains a bytes object)
    payload = {"blob": b"not-json"}
    raw = FakeRawEmail(raw_bytes=b"ok", mailbox="INBOX", uid=2, uidvalidity="v1", raw_payload=payload)
    metadata = {"message_id": "msg-2"}

    # Should not raise
    repo.persist_raw_message("tenant-a", raw, metadata)

    engine = repo.engine
    with Session(engine) as session:
        res = session.execute(text("SELECT id, raw_payload FROM imap_raw_events WHERE message_id = :mid"), {"mid": "msg-2"}).first()
        assert res is not None
        stored = res[1]
        # For non-serializable payload the repository is expected to store NULL.
        # SQLite/SQLAlchemy may return the literal string 'null' or None; accept both.
        if isinstance(stored, str):
            try:
                parsed = json.loads(stored)
            except Exception:
                parsed = None
            assert parsed is None
        else:
            assert stored is None
