# app/integrations/llm_service.py
"""
Simple stub for LLM service used in tests.
Provides `classify_event` and `extract_entities` functions.
"""
from typing import Dict, Any


def classify_event(raw_event) -> str:
    """Return a simple classification for the event."""
    # Accept RawEvent object and extract subject
    subject = getattr(raw_event, "subject", None) or ""
    body = getattr(raw_event, "raw_text", None) or ""
    
    if "preventivo" in subject.lower() or "prevent" in subject.lower():
        return "new_quote"
    if "preventivo" in body.lower():
        return "new_quote"
    return "unknown"


def extract_entities(raw_event) -> Dict[str, Any]:
    """Fake entity extraction for tests."""
    # Accept RawEvent object and extract from text
    return {"nome": "Test", "cognome": "User"}

