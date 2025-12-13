"""
app/file_access/watchers/smb_watcher.py

Polling-based SMB file watcher.

Provides a lightweight polling watcher that detects created, modified and deleted
files on a FileStorageProvider (SMB adapter). It's async and calls registered
callbacks on change events.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.file_access.base_fs import FileInfo, FileStorageProvider
from app.monitoring.logger import log


@dataclass
class FileChangeEvent:
    """Represents a file system change detected by the watcher."""
    type: str  # 'created' | 'modified' | 'deleted'
    path: str
    info: Optional[Dict[str, Any]] = None


class SMBWatcher:
    """Polling watcher for SMB (or any FileStorageProvider that implements list_files).

    Usage:
        watcher = SMBWatcher(provider, interval=5.0)
        watcher.subscribe(callback)
        await watcher.start()

    The callback may be either a normal function or an async callable that
    accepts a single `FileChangeEvent` argument.
    """

    def __init__(
        self,
        provider: FileStorageProvider,
        base_path: str = "/",
        interval: float = 5.0,
        recursive: bool = True,
        pattern: Optional[str] = None,
    ) -> None:
        self.provider = provider
        self.base_path = base_path
        self.interval = float(interval)
        self.recursive = recursive
        self.pattern = pattern

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._callbacks: List[Callable[[FileChangeEvent], Any]] = []
        # snapshot: path -> (modified_ts_iso, size)
        self._snapshot: Dict[str, Tuple[Optional[str], Optional[int]]] = {}

    def subscribe(self, callback: Callable[[FileChangeEvent], Any]) -> None:
        """Register a callback to be called when an event is detected."""
        self._callbacks.append(callback)

    def unsubscribe(self, callback: Callable[[FileChangeEvent], Any]) -> None:
        """Unregister a previously registered callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    async def start(self, connect: bool = True) -> None:
        """Start the watcher background task.

        Args:
            connect: if True, call provider.connect() before polling.
        """
        if self._running:
            return
        self._running = True
        try:
            if connect and hasattr(self.provider, "connect"):
                await self.provider.connect()

            # build initial snapshot
            self._snapshot = await self._build_snapshot()

            self._task = asyncio.create_task(self._poll_loop())
            log("INFO", "SMBWatcher started", module="smb_watcher")
        except Exception as e:
            log("ERROR", f"SMBWatcher failed to start: {e}", module="smb_watcher")
            self._running = False

    async def stop(self, disconnect: bool = True) -> None:
        """Stop the watcher and optionally disconnect provider."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if disconnect and hasattr(self.provider, "disconnect"):
            try:
                await self.provider.disconnect()
            except Exception:
                pass
        log("INFO", "SMBWatcher stopped", module="smb_watcher")

    async def _build_snapshot(self) -> Dict[str, Tuple[Optional[str], Optional[int]]]:
        """List files and build a simple snapshot mapping path -> (mtime_iso, size)."""
        snapshot: Dict[str, Tuple[Optional[str], Optional[int]]] = {}
        try:
            files = await self.provider.list_files(self.base_path, pattern=self.pattern, recursive=self.recursive)
            for fi in files:
                # tolerate different field names from implementations
                mtime = None
                size = None
                # try several attribute names
                for attr in ("modified_time", "modified_at", "last_modified"):
                    m = getattr(fi, attr, None)
                    if m:
                        if isinstance(m, datetime):
                            mtime = m.isoformat()
                        else:
                            mtime = str(m)
                        break
                for attr in ("size", "file_size", "size_bytes"):
                    s = getattr(fi, attr, None)
                    if s is not None:
                        size = int(s)
                        break

                snapshot[fi.path] = (mtime, size)
        except Exception as e:
            log("ERROR", f"SMBWatcher snapshot failed: {e}", module="smb_watcher")
        return snapshot

    async def _poll_loop(self) -> None:
        """Poll loop that detects created/modified/deleted files and dispatches events."""
        try:
            while self._running:
                try:
                    current = await self._build_snapshot()

                    # detect created and modified
                    for path, (mtime, size) in current.items():
                        if path not in self._snapshot:
                            evt = FileChangeEvent(type="created", path=path, info={"mtime": mtime, "size": size})
                            await self._dispatch(evt)
                        else:
                            prev_mtime, prev_size = self._snapshot[path]
                            if mtime != prev_mtime or size != prev_size:
                                evt = FileChangeEvent(type="modified", path=path, info={"mtime": mtime, "size": size, "prev_mtime": prev_mtime, "prev_size": prev_size})
                                await self._dispatch(evt)

                    # detect deleted
                    for path in list(self._snapshot.keys()):
                        if path not in current:
                            evt = FileChangeEvent(type="deleted", path=path, info=None)
                            await self._dispatch(evt)

                    self._snapshot = current
                except Exception as e:
                    log("ERROR", f"SMBWatcher poll error: {e}", module="smb_watcher")

                await asyncio.sleep(self.interval)
        except asyncio.CancelledError:
            return

    async def _dispatch(self, event: FileChangeEvent) -> None:
        """Call registered callbacks with the event. Supports sync and async callbacks."""
        for cb in list(self._callbacks):
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(event)
                else:
                    # run sync callback in threadpool to avoid blocking
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, cb, event)
            except Exception as e:
                log("ERROR", f"SMBWatcher callback error: {e}", module="smb_watcher")
