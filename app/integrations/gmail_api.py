# app/integrations/gmail_api.py
"""
Gmail API connector for Edilcos Automation Backend.
"""
import base64
import email
import aiohttp
from typing import Dict, Any, List, Optional
from app.monitoring.errors import record_error

# Placeholder for Google API client setup
# In production, use google-auth, google-api-python-client, etc.

async def fetch_message(message_id: str, access_token: str) -> Dict[str, Any]:
    """
    Fetch Gmail message and parse MIME content.
    Args:
        message_id: Gmail message ID
        access_token: OAuth2 token or service account token
    Returns:
        Dict with subject, sender, text_plain, text_html, attachments metadata
    """
    url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}?format=raw"
    headers = {"Authorization": f"Bearer {access_token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            try:
                resp.raise_for_status()
            except Exception as exc:
                tb = None
                try:
                    tb = exc.__traceback__
                except Exception:
                    tb = None
                await record_error("gmail_api", "fetch_message", f"Gmail API request failed: {exc}", details={"message_id": message_id}, stacktrace=None)
                raise
            data = await resp.json()
            raw = data.get("raw")
            if not raw:
                raise ValueError("No raw MIME data returned from Gmail API")
            mime_bytes = base64.urlsafe_b64decode(raw)
            msg = email.message_from_bytes(mime_bytes)
            subject = msg.get("Subject")
            sender = msg.get("From")
            text_plain = None
            text_html = None
            attachments = []
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain" and not text_plain:
                    text_plain = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="replace")
                elif content_type == "text/html" and not text_html:
                    text_html = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="replace")
                elif part.get_filename():
                    attachments.append({
                        "filename": part.get_filename(),
                        "mime_type": content_type,
                        "size_bytes": len(part.get_payload(decode=True) or b""),
                        "attachment_id": part.get("X-Attachment-Id")
                    })
            return {
                "subject": subject,
                "sender": sender,
                "text_plain": text_plain,
                "text_html": text_html,
                "attachments": attachments,
                "raw_mime": raw
            }
