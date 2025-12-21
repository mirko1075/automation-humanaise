# tests/test_auth_google_callback.py
"""
Tests for the Google OAuth callback placeholder endpoint.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_google_callback_missing_code():
    resp = client.get("/auth/google/callback")
    assert resp.status_code == 400
    assert resp.json().get("detail") == "Missing 'code' query parameter"


def test_google_callback_with_code():
    resp = client.get("/auth/google/callback?code=abc123")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "note" in data
