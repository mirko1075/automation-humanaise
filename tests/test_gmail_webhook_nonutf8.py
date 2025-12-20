import base64
import json
import pytest
from fastapi.testclient import TestClient

from app.main import app


def make_malformed_base64_payload():
    # create bytes that are invalid UTF-8 sequences
    bad_bytes = b"\x81\x84\x95\x00\x7b\x22historyId\x22\x3a\x22h1\x22\x7d"
    # base64 urlsafe encode
    b64 = base64.urlsafe_b64encode(bad_bytes).decode().rstrip("=")
    return {"message": {"data": b64}}


def test_gmail_webhook_handles_non_utf8_payload_no_500():
    client = TestClient(app)
    payload = make_malformed_base64_payload()
    resp = client.post("/gmail/webhook", json=payload)
    # Should not return 500; acceptable responses are 200/received or 404 if tenant not found
    assert resp.status_code in (200, 404, 202, 400)
    # If payload was stored as raw base64 we expect it not to cause a server error
    # and possibly contain our marker in the DB; here we just ensure no 500
    assert resp.status_code != 500
