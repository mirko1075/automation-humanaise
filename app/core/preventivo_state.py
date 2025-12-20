# app/core/preventivo_state.py
"""
Preventivo (quote) state machine (v1).

Defines allowed states and transitions. Validation is centralized via
`validate_transition(from_status, to_status)` which raises ValueError on invalid
transitions.

# TODO(state-machine): aggiungere storico transizioni
# TODO(onedrive): creare struttura cartelle al cambio stato
# TODO(notifications): notificare operatore/cliente al cambio stato
# TODO(monitoring): tracciare cambi stato falliti
"""
from enum import Enum
from typing import Dict, List


class PreventivoStatus(str, Enum):
    NEW = "NEW"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_CUSTOMER = "WAITING_CUSTOMER"
    SENT = "SENT"
    WON = "WON"
    LOST = "LOST"
    CANCELLED = "CANCELLED"


# Allowed transitions map: from -> list of allowed to states
_TRANSITIONS: Dict[PreventivoStatus, List[PreventivoStatus]] = {
    PreventivoStatus.NEW: [PreventivoStatus.IN_PROGRESS, PreventivoStatus.WAITING_CUSTOMER, PreventivoStatus.SENT, PreventivoStatus.CANCELLED],
    PreventivoStatus.IN_PROGRESS: [PreventivoStatus.WAITING_CUSTOMER, PreventivoStatus.SENT, PreventivoStatus.CANCELLED],
    PreventivoStatus.WAITING_CUSTOMER: [PreventivoStatus.IN_PROGRESS, PreventivoStatus.SENT, PreventivoStatus.CANCELLED],
    PreventivoStatus.SENT: [PreventivoStatus.IN_PROGRESS, PreventivoStatus.WAITING_CUSTOMER, PreventivoStatus.WON, PreventivoStatus.LOST, PreventivoStatus.CANCELLED],
    # Terminal states - no outgoing transitions
    PreventivoStatus.WON: [],
    PreventivoStatus.LOST: [],
    PreventivoStatus.CANCELLED: [],
}


def validate_transition(from_status: str, to_status: str) -> bool:
    """
    Validate that a transition from `from_status` to `to_status` is allowed.

    Args:
        from_status: current/previous status (string or PreventivoStatus)
        to_status: desired next status (string or PreventivoStatus)

    Returns:
        True if allowed.

    Raises:
        ValueError if transition is not allowed.
    """
    if from_status is None:
        # Creation -> allow only NEW (or implicit mapping)
        if to_status == PreventivoStatus.NEW.value:
            return True
        raise ValueError(f"Invalid initial status: {to_status}; must be {PreventivoStatus.NEW.value}")

    # Normalize to enum values
    try:
        src = PreventivoStatus(from_status)
    except Exception:
        # Accept legacy values mapping (e.g., OPEN -> NEW)
        if str(from_status).upper() == "OPEN":
            src = PreventivoStatus.NEW
        else:
            raise ValueError(f"Unknown from_status: {from_status}")

    try:
        dst = PreventivoStatus(to_status)
    except Exception:
        if str(to_status).upper() == "OPEN":
            dst = PreventivoStatus.NEW
        else:
            raise ValueError(f"Unknown to_status: {to_status}")

    allowed = _TRANSITIONS.get(src, [])
    if dst in allowed:
        return True
    raise ValueError(f"Invalid transition from {src.value} to {dst.value}")


def allowed_transitions(from_status: str) -> List[str]:
    """Return list of allowed destination status names for a given from_status."""
    try:
        src = PreventivoStatus(from_status)
    except Exception:
        if str(from_status).upper() == "OPEN":
            src = PreventivoStatus.NEW
        else:
            return []
    return [s.value for s in _TRANSITIONS.get(src, [])]
