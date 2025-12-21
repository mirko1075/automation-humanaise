import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ingestors.imap.repository import IMAPRawEvent, IMAPRepository, Base


def test_repository_dedup(tmp_path, monkeypatch):
    # Use a temporary SQLite file to simulate DB
    db_file = tmp_path / 'test.db'
    url = f"sqlite:///{db_file}"
    engine = create_engine(url)
    Base.metadata.create_all(bind=engine)

    # Monkeypatch env DATABASE_URL to point at our SQLite DB
    monkeypatch.setenv('DATABASE_URL', url)

    repo = IMAPRepository(database_url=url)

    # Persist first event
    raw = b'rawbytes'
    meta = {'message_id': 'm1', 'subject': 's1'}
    id1 = repo.persist_raw('t1', 'INBOX', 1, 'v1', raw, meta)
    assert id1 is not None

    # Duplicate insert should return None
    id2 = repo.persist_raw('t1', 'INBOX', 1, 'v1', raw, meta)
    assert id2 is None
