# ingestors/graph/graph_mail_client.py
"""
GraphMailClient: Fetches mail from Microsoft Graph and yields RawEmail objects.
"""
import requests
from datetime import datetime
from typing import Iterable, List, Optional
from ingestors.mail.base_client import BaseMailClient
from ingestors.imap.models import RawEmail, Attachment
from .auth import GraphAuthProvider

class GraphMailClient(BaseMailClient):
    def __init__(self, user_principal_name: str, mailbox: str = "Inbox"):
        self.user_principal_name = user_principal_name
        self.mailbox = mailbox
        self.auth = GraphAuthProvider()
        self.session = None
        self._connected = False

    def connect(self):
        token = self.auth.get_access_token()
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        })
        self._connected = True

    def fetch_messages(self) -> Iterable[RawEmail]:
        if not self._connected or self.session is None:
            raise RuntimeError("GraphMailClient not connected. Call connect() before fetching messages.")
        url = (
            f"https://graph.microsoft.com/v1.0/"
            f"users/{self.user_principal_name}/"
            f"mailFolders/{self.mailbox}/messages"
        )
        resp = self.session.get(url)
        resp.raise_for_status()
        data = resp.json()
        for msg in data.get("value", []):
            yield self._to_raw_email(msg)

    def disconnect(self):
        if self.session:
            self.session.close()
        self._connected = False

    def _to_raw_email(self, msg: dict) -> RawEmail:
        attachments: List[Attachment] = []
        for att in msg.get("attachments", []):
            if att.get("isInline"):
                continue
            attachments.append(Attachment(
                filename=att.get("name"),
                content_type=att.get("contentType"),
                data=att.get("contentBytes", b"")
            ))
        return RawEmail(
            tenant_id="graph",  # or configurable
            mailbox=self.mailbox,
            uid=0,  # Graph does not use UID, can use hash or 0
            uidvalidity="graph",
            message_id=msg.get("id"),
            subject=msg.get("subject"),
            from_=msg.get("from", {}).get("emailAddress", {}).get("address"),
            to=[r.get("emailAddress", {}).get("address") for r in msg.get("toRecipients", [])],
            date=datetime.fromisoformat(msg.get("receivedDateTime")) if msg.get("receivedDateTime") else None,
            text=msg.get("body", {}).get("content") if msg.get("body", {}).get("contentType") == "text" else None,
            html=msg.get("body", {}).get("content") if msg.get("body", {}).get("contentType") == "html" else None,
            attachments=attachments
        )
