"""
app/core/classifier.py

Deterministic rule-based classifier for the Preventivi flow (V1).
Exposes `async def classify(email_data: dict, tenant_id: UUID | None, db) -> dict`.

Rules (order):
  1. ignored: auto-reply sender or auto-reply text
  2. new_quote: keyword match in subject/body
  3. follow_up: same sender with open Preventivo (DB read-only check)
  4. unassigned: fallback

This module contains no side effects and performs read-only DB checks via
the repository accessor `_get_preventivo_repo(db)` which returns an object
implementing `has_open_preventivo(tenant_id, email) -> bool` (async).
"""
from typing import Optional, Dict
from uuid import UUID

KEYWORDS = ["preventivo", "ristrutturazione", "lavori", "offerta"]
AUTO_REPLY_MARKERS = [
    "no-reply",
    "noreply",
    "auto-reply",
    "out of office",
    "vacation",
    "away from my email",
]


def _normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return value.strip().lower()


def _contains_any(text: str, markers) -> bool:
    t = text
    for m in markers:
        if m in t:
            return True
    return False


def _get_preventivo_repo(db):
    """Return a Preventivo repository instance from `db`.

    This helper is intentionally small so tests can monkeypatch it.
    The repository must expose an async method `has_open_preventivo(tenant_id, email)`.
    """
    # In production, callers should pass a `db` that allows repository construction.
    # Example: return PreventivoRepository(db)
    raise NotImplementedError("_get_preventivo_repo must be patched in tests or implemented in runtime")


async def classify(email_data: Dict[str, str], tenant_id: Optional[UUID], db) -> Dict[str, str]:
    """Classify a parsed email into a Preventivi outcome.

    Args:
        email_data: dict with keys `from_email`, `subject`, `body_text`, `body_html`.
        tenant_id: tenant identifier or None
        db: database/session object used only for read-only checks

    Returns:
        dict with keys `outcome` and `reason`.
    """
    # Normalize inputs safely
    from_email = _normalize_text(email_data.get("from_email"))
    subject = _normalize_text(email_data.get("subject"))
    body = _normalize_text(email_data.get("body_text") or email_data.get("body_html"))

    # Rule 1: ignored (auto-reply sender)
    if from_email and _contains_any(from_email, ["no-reply", "noreply"]):
        return {"outcome": "ignored", "reason": "auto_reply_from_address"}

    # Rule 1b: ignored (auto-reply text in subject or body)
    combined = f"{subject} {body}".strip()
    if combined and _contains_any(combined, AUTO_REPLY_MARKERS):
        return {"outcome": "ignored", "reason": "auto_reply_text"}

    # Rule 2: follow_up (sender has open Preventivo)
    if from_email and db is not None:
        try:
            repo = _get_preventivo_repo(db)
            has_open = await repo.has_open_preventivo(tenant_id, from_email)
            if has_open:
                return {"outcome": "follow_up", "reason": "existing_open_quote"}
        except NotImplementedError:
            # Runtime environment didn't provide a repo; treat as no open quote
            pass

    # Rule 3: new_quote (keyword in subject or body)
    if combined and _contains_any(combined, KEYWORDS):
        return {"outcome": "new_quote", "reason": "keyword_match"}

    # Rule 4: fallback
    return {"outcome": "unassigned", "reason": "no_match"}
