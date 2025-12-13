# app/integrations/llm_service.py
"""
Simple stub for LLM service used in tests.
Provides `classify_event` and `extract_entities` functions.
"""
from typing import Dict, Any


def classify_event(raw_event) -> str:
    """Return a simple classification for the event."""
    # Accept both RawEvent (payload) and NormalizedEvent (normalized_data)
    payload = getattr(raw_event, "payload", None)
    if not payload:
        payload = getattr(raw_event, "normalized_data", {}) or {}
    subject = payload.get("subject", "") or ""
    body = payload.get("text_plain", "") or payload.get("body", "") or ""
    # Debug logging
    print(f"[LLM DEBUG] payload type: {type(payload)}")
    print(f"[LLM DEBUG] payload keys: {payload.keys() if isinstance(payload, dict) else 'not dict'}")
    print(f"[LLM DEBUG] subject: {subject}")
    print(f"[LLM DEBUG] body: {body[:100] if body else 'empty'}")
    if "preventivo" in subject.lower() or "prevent" in subject.lower():
        return "new_quote"
    if "preventivo" in body.lower():
        return "new_quote"
    return "unknown"


def extract_entities(raw_event) -> Dict[str, Any]:
    """Fake entity extraction for tests."""
    # Accept both RawEvent (payload) and NormalizedEvent (normalized_data)
    payload = getattr(raw_event, "payload", None)
    if not payload:
        payload = getattr(raw_event, "normalized_data", {}) or {}
    # Example extraction: try to get name, email, phone from body
    body = payload.get("text_plain", "") or payload.get("body", "") or ""
    import re
    name = ""
    email = ""
    phone = ""
    # Simple regex extraction
    email_match = re.search(r"[\w\.-]+@[\w\.-]+", body)
    if email_match:
        email = email_match.group(0)
    phone_match = re.search(r"\b\d{3}[- .]?\d{6,7}\b", body)
    if phone_match:
        phone = phone_match.group(0)
    name_match = re.search(r"sono ([A-Za-z ]+)[,\.]", body, re.IGNORECASE)
    if name_match:
        name = name_match.group(1).strip()
    return {"nome": name or "Test", "email": email, "phone": phone}

