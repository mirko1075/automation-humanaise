import pytest
import asyncio

from uuid import UUID


@pytest.mark.asyncio
async def test_ignored_no_reply_email():
    from app.core import classifier

    email = {
        "from_email": "noreply@service.example.com",
        "subject": "Your receipt",
        "body_text": "This is an automated message",
    }

    result = await classifier.classify(email, None, db=None)

    assert result["outcome"] == "ignored"
    assert result["reason"] == "auto_reply_from_address"


@pytest.mark.asyncio
async def test_ignored_auto_reply_text():
    from app.core import classifier

    email = {
        "from_email": "john@example.com",
        "subject": "Out of office",
        "body_text": "I am currently out of office until next week",
    }

    result = await classifier.classify(email, None, db=None)

    assert result["outcome"] == "ignored"
    assert result["reason"] == "auto_reply_text"


@pytest.mark.asyncio
async def test_new_quote_keyword_in_subject():
    from app.core import classifier

    email = {
        "from_email": "client@example.com",
        "subject": "Richiesta preventivo per ristrutturazione",
        "body_text": "Please provide a quote",
    }

    result = await classifier.classify(email, UUID(int=0), db=None)

    assert result["outcome"] == "new_quote"
    assert result["reason"] == "keyword_match"


@pytest.mark.asyncio
async def test_new_quote_keyword_in_body():
    from app.core import classifier

    email = {
        "from_email": "client2@example.com",
        "subject": "Question",
        "body_text": "Vorrei un preventivo per lavori in bagno",
    }

    result = await classifier.classify(email, UUID(int=0), db=None)

    assert result["outcome"] == "new_quote"
    assert result["reason"] == "keyword_match"


class FakePreventivoRepo:
    def __init__(self, has_open: bool):
        self._has_open = has_open

    async def has_open_preventivo(self, tenant_id, email):
        return self._has_open


@pytest.mark.asyncio
async def test_follow_up_existing_open_quote(monkeypatch):
    from app.core import classifier

    email = {
        "from_email": "repeat@example.com",
        "subject": "Re: preventivo",
        "body_text": "Following up on my previous request",
    }

    # Provide a fake DB object that classifier will use to query
    fake_repo = FakePreventivoRepo(has_open=True)

    class FakeDB:
        def __init__(self, repo):
            self.repo = repo

    fake_db = FakeDB(fake_repo)

    # Monkeypatch the repository constructor used in classifier
    monkeypatch.setattr(classifier, "_get_preventivo_repo", lambda db: db.repo)

    result = await classifier.classify(email, UUID(int=1), db=fake_db)

    assert result["outcome"] == "follow_up"
    assert result["reason"] == "existing_open_quote"


@pytest.mark.asyncio
async def test_unassigned_fallback(monkeypatch):
    from app.core import classifier

    email = {
        "from_email": "someone@example.com",
        "subject": "Hello",
        "body_text": "Just saying hi",
    }

    fake_repo = FakePreventivoRepo(has_open=False)

    class FakeDB:
        def __init__(self, repo):
            self.repo = repo

    fake_db = FakeDB(fake_repo)
    monkeypatch.setattr(classifier, "_get_preventivo_repo", lambda db: db.repo)

    result = await classifier.classify(email, UUID(int=2), db=fake_db)

    assert result["outcome"] == "unassigned"
    assert result["reason"] == "no_match"
