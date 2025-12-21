"""Stub LLM service for Normalizer V1.

This module provides a minimal `classify_event` function so tests and
runtime code can import and patch it. It intentionally contains no
external dependencies and returns a conservative default classification.
"""
from typing import Dict


async def classify_event(email_data: Dict) -> str:
    """Classify event using LLM heuristics.

    This is a minimal stub used for tests and to allow the runtime
    import path `app.core.normalizer.llm_service.classify_event`.

    Returns:
        A string outcome such as 'new_quote', 'follow_up', 'ignored', 'unassigned'.
    """
    # Heuristic stub used by tests: if subject or body mentions 'preventivo'
    # (Italian for 'quote') return 'new_quote' to allow deterministic
    # behavior in unit tests. Otherwise return a conservative 'unassigned'.
    try:
        subj = (email_data.get("subject") or email_data.get("headers", {}).get("subject") or "") if isinstance(email_data, dict) else ""
        body = (email_data.get("body_text") or email_data.get("text_plain") or "") if isinstance(email_data, dict) else ""
        combined = f"{subj} {body}".lower()
        if "preventivo" in combined or "preventivi" in combined or "quotation" in combined:
            return "new_quote"
    except Exception:
        pass
    # Conservative default: unassigned
    return "unassigned"


async def extract_entities(email_data: Dict) -> Dict:
    """Extract named entities from email text.

    Minimal stub used for tests. Returns an empty dict by default.
    Tests may patch this function to return expected fields.
    """
    return {}
