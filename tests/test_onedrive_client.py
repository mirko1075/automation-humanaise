"""Unit tests for app.integrations.onedrive_client.OneDriveClient

These tests mock a minimal aiohttp-like session object so we can exercise
the client's logic without performing network requests.
"""
import asyncio
import tempfile
from pathlib import Path

import pytest

from app.integrations.onedrive_client import OneDriveClient, TestTokenAuth


class FakeContent:
    def __init__(self, chunks: list[bytes]):
        self._chunks = chunks

    async def iter_chunked(self, n):
        for c in self._chunks:
            yield c


class FakeResp:
    def __init__(self, status=200, json_payload=None, text_payload="", content_chunks=None):
        self.status = status
        self._json = json_payload or {}
        self._text = text_payload
        self.content = FakeContent(content_chunks or [b""])

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self):
        return self._json

    async def text(self):
        return self._text


class FakeSession:
    def __init__(self, responses: dict[str, FakeResp]):
        self._responses = responses
        self.closed = False

    def _resp_for(self, url: str):
        # simple matching by suffix; allow method-prefixed keys like "GET :/content"
        for k, v in self._responses.items():
            if " " in k:
                # method-specific key, e.g. "GET :/content"
                _, suffix = k.split(" ", 1)
                if url.endswith(suffix):
                    return v
        for k, v in self._responses.items():
            # fallback to suffix-only key
            if url.endswith(k):
                return v
        return FakeResp()

    def get(self, url):
        return self._resp_for(url)

    def put(self, url, data=None):
        return self._resp_for(url)

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_list_and_get_file_metadata():
    fake_list = {"value": [{"id": "1", "name": "a.txt"}]}
    fake_meta = {"id": "1", "name": "a.txt", "size": 123}
    responses = {
        ":/children": FakeResp(status=200, json_payload=fake_list),
        "": FakeResp(status=200, json_payload=fake_meta),
    }

    session = FakeSession(responses)
    client = OneDriveClient(session=session)

    items = await client.list_files("folder")
    assert isinstance(items, list)
    assert items[0]["name"] == "a.txt"

    meta = await client.get_file_metadata("folder/a.txt")
    assert meta["name"] == "a.txt"


@pytest.mark.asyncio
async def test_download_and_upload_file(tmp_path):
    # prepare fake content chunks and responses
    file_bytes = b"hello world"
    dl_resp = FakeResp(status=200, content_chunks=[file_bytes])
    up_resp = FakeResp(status=200, json_payload={"id": "uploaded"})
    # method-specific keys so we can return different responses for GET vs PUT
    responses = {
        "GET :/content": dl_resp,
        "PUT :/content": up_resp,
    }

    session = FakeSession(responses)
    client = OneDriveClient(session=session)

    local = tmp_path / "out.bin"
    await client.download_file("some/path/file.bin", str(local))
    assert local.exists()
    assert local.read_bytes() == file_bytes

    # create a small file for upload
    upload_file = tmp_path / "u.bin"
    upload_file.write_bytes(b"upload-data")
    res = await client.upload_file(str(upload_file), "some/path/u.bin")
    assert isinstance(res, dict)
