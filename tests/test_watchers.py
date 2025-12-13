# tests/test_watchers.py
import asyncio
import pytest
from typing import Dict, Any
from app.file_access.watchers.smb_watcher import SMBWatcher, FileChangeEvent


class DummyProvider:
    def __init__(self, files: Dict[str, Dict[str, Any]]):
        # files: path -> {"mtime": iso, "size": int}
        self._files = files

    async def connect(self):
        return

    async def disconnect(self):
        return

    async def list_files(self, path, pattern=None, recursive=False):
        class FI:
            def __init__(self, path, mtime, size):
                self.path = path
                self.modified_time = mtime
                self.size = size

        return [FI(p, d["mtime"], d["size"]) for p, d in self._files.items()]


@pytest.mark.asyncio
async def test_watcher_detects_created_modified_deleted():
    # initial files
    files = {"/a.txt": {"mtime": "t1", "size": 10}}
    provider = DummyProvider(files.copy())
    watcher = SMBWatcher(provider, interval=0.2)

    events = []

    async def cb(evt: FileChangeEvent):
        events.append((evt.type, evt.path))

    watcher.subscribe(cb)
    await watcher.start(connect=False)

    # wait one cycle
    await asyncio.sleep(0.25)

    # create new file
    provider._files["/b.txt"] = {"mtime": "t2", "size": 5}
    await asyncio.sleep(0.25)

    # modify existing
    provider._files["/a.txt"]["mtime"] = "t3"
    await asyncio.sleep(0.25)

    # delete file
    del provider._files["/a.txt"]
    await asyncio.sleep(0.25)

    await watcher.stop()

    types = [t for t, _ in events]
    paths = [p for _, p in events]

    assert ("created" in types) and ("/b.txt" in paths)
    assert ("modified" in types) and ("/a.txt" in paths)
    assert ("deleted" in types) and ("/a.txt" in paths)
