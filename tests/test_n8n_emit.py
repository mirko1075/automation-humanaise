import pytest
from unittest.mock import patch

from ingestors.imap.n8n_emit import emit_to_n8n


def make_message():
    return {
        "id": "evt-1",
        "source": {"account_id": "tenant-1", "message_uid": "uid-1"},
        "content": "hello",
    }


def test_emit_to_n8n_handles_404(monkeypatch):
    class DummyResp:
        status_code = 404
        text = "Not Found"

        def raise_for_status(self):
            from requests import HTTPError

            raise HTTPError("404 Client Error: Not Found")

    class DummySession:
        def post(self, url, json, timeout):
            return DummyResp()

        def close(self):
            pass
        def mount(self, prefix, adapter):
            # no-op for test
            return

    monkeypatch.setenv("N8N_WEBHOOK_URL", "https://n8n.humanaise.com/webhook-test/abc")
    with patch("ingestors.imap.n8n_emit.requests.Session", return_value=DummySession()):
        # Should not raise despite a 404 from the remote
        emit_to_n8n(make_message())
