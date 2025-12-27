"""
ingestors/imap/imap_client.py

IMAP client wrapper using `imaplib`. Provides connection management and
incremental fetch based on UID and UIDVALIDITY.
"""
from __future__ import annotations

import imaplib
import os
import logging
from typing import Optional, Tuple, List

logger = logging.getLogger("ingestors.imap.imap_client")


class IMAPClient:
    """Simple blocking IMAP client.

    Environment variables used:
    - IMAP_HOST, IMAP_PORT, IMAP_USER, IMAP_PASSWORD
    """

    def __init__(self, host: Optional[str] = None, port: Optional[int] = None, use_ssl: bool = True):
        self.host = host or os.environ.get("IMAP_HOST")
        self.port = port or int(os.environ.get("IMAP_PORT", "993"))
        self.user = os.environ.get("IMAP_USER")
        self.password = os.environ.get("IMAP_PASSWORD")
        self.use_ssl = use_ssl
        self._conn: Optional[imaplib.IMAP4_SSL | imaplib.IMAP4] = None

    def connect(self):
        print("IMAP CONNECT CALLED", self.host, self.user)
        try:
            self._connect_internal()
        except Exception as e:
            print("EXCEPTION in connect", e)
            import traceback
            traceback.print_exc()
            logger.exception("imap_connection_exception")
            raise

    def _connect_internal(self):
        try:
            if self._conn:
                return
            logger.info("connecting_imap", **{"host": self.host, "port": self.port})
            if not self.host:
                raise ValueError("IMAP host must be provided (via argument or IMAP_HOST env var)")
            if self.use_ssl:
                self._conn = imaplib.IMAP4_SSL(self.host, self.port)
            else:
                self._conn = imaplib.IMAP4(self.host, self.port)
            if self.user and self.password:
                try:
                    print("IMAP LOGIN CALLED", self.host, self.user, self.password)
                    typ, data = self._conn.login(self.user, self.password)
                    logger.info("imap_login", extra={"result": typ})
                except imaplib.IMAP4.error as e:
                    print("EXCEPTION in _connect_internal (login)", e)
                    import traceback
                    traceback.print_exc()
                    logger.exception("imap_login_failed", extra={"user": self.user})
                    raise
            else:
                raise ValueError("IMAP user and password must be provided (via env vars IMAP_USER and IMAP_PASSWORD)")
        except Exception as e:
            print("EXCEPTION in _connect_internal", e)
            import traceback
            traceback.print_exc()
            raise

    def logout(self):
        if self._conn:
            try:
                self._conn.logout()
            except Exception:
                logger.exception("imap_logout_failed")
            finally:
                self._conn = None

    def select_mailbox(self, mailbox: str = "INBOX") -> Tuple[int, str]:
        """Select a mailbox and return (message_count, uidvalidity).

        Returns (message_count, uidvalidity)
        """
        assert self._conn, "IMAP not connected"
        typ, data = self._conn.select(mailbox, readonly=True)
        if typ != "OK":
            raise RuntimeError(f"Failed to select mailbox {mailbox}: {typ} {data}")
        # Parse response: data[0] like b'123'
        message_count = int(data[0].decode()) if data and data[0] else 0
        # Fetch UIDVALIDITY
        typ, resp = self._conn.status(mailbox, '(UIDVALIDITY)')
        uidvalidity = ""
        if typ == 'OK' and resp and isinstance(resp, list):
            # resp example: [b'INBOX (UIDVALIDITY 159753)']
            try:
                txt = resp[0].decode()
                parts = txt.split()
                uidvalidity = parts[parts.index('UIDVALIDITY') + 1].strip(')')
            except Exception:
                uidvalidity = ""
        return message_count, uidvalidity

    def fetch_uids_since(self, since_uid: Optional[int] = None) -> List[int]:
        """Return list of UIDs greater than since_uid. If since_uid is None, returns all UIDs."""
        assert self._conn, "IMAP not connected"
        typ, data = self._conn.uid('SEARCH', 'ALL')
        if typ != 'OK':
            raise RuntimeError(f"UID SEARCH failed: {typ} {data}")
        if not data or not data[0]:
            return []
        uid_list = [int(x) for x in data[0].split()]
        if since_uid is None:
            return uid_list
        return [u for u in uid_list if u > since_uid]

    def fetch_message_by_uid(self, uid: int) -> Tuple[bytes, dict]:
        """Fetch the full RFC822 message for the given UID.

        Returns (raw_bytes, metadata)
        metadata will include 'UID' and 'INTERNALDATE' when available.
        """
        assert self._conn, "IMAP not connected"
        typ, data = self._conn.uid('FETCH', str(uid), '(RFC822 INTERNALDATE BODY.PEEK[HEADER.FIELDS (MESSAGE-ID SUBJECT FROM TO DATE)])')
        if typ != 'OK':
            raise RuntimeError(f"UID FETCH failed for {uid}: {typ} {data}")
        raw = b''
        meta = {}
        # data is a list of tuples
        for part in data:
            if isinstance(part, tuple) and part[1]:
                raw += part[1]
        # Try to extract simple metadata via a separate fetch for header only
        return raw, meta
