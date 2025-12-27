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
        # Make tenant_id available to produced RawEmail instances
        self.tenant_id = getattr(self.auth, "tenant_id", "graph")

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
        # extract body content intelligently
        body = None
        html = None
        body_obj = msg.get("body", {}) or {}
        if body_obj.get("contentType") == "text":
            body = body_obj.get("content")
        elif body_obj.get("contentType") == "html":
            html = body_obj.get("content")

        # recipients
        to_list = [r.get("emailAddress", {}).get("address") for r in msg.get("toRecipients", [])]
        cc_list = [r.get("emailAddress", {}).get("address") for r in msg.get("ccRecipients", [])]
        bcc_list = [r.get("emailAddress", {}).get("address") for r in msg.get("bccRecipients", [])]

        received = None
        if msg.get("receivedDateTime"):
            try:
                received = datetime.fromisoformat(msg.get("receivedDateTime"))
            except Exception:
                received = None

        return RawEmail(
            tenant_id=self.tenant_id,
            mailbox=self.mailbox,
            uid=msg.get("id"),
            uidvalidity="graph",
            message_id=msg.get("id"),
            subject=msg.get("subject"),
            from_=msg.get("from", {}).get("emailAddress", {}).get("address"),
            to=to_list,
            date=received,
            text=body,
            html=html,
            attachments=attachments,
            # populate adapter-required optional fields
            event_id=msg.get("id"),
            received_at=received,
            cc=cc_list or None,
            bcc=bcc_list or None,
            headers=msg.get("internetMessageHeaders", None),
            raw_payload=msg,
        )
