"""
Unit tests for the Preventivo state machine in app/core/preventivo_state.py
"""
from app.core.preventivo_state import validate_transition, allowed_transitions, PreventivoStatus


def test_validate_valid_transitions():
    # Basic allowed transition NEW -> IN_PROGRESS
    assert validate_transition(None, PreventivoStatus.NEW.value) is True
    assert validate_transition(PreventivoStatus.NEW.value, PreventivoStatus.IN_PROGRESS.value) is True
    assert validate_transition(PreventivoStatus.SENT.value, PreventivoStatus.WON.value) is True


def test_validate_invalid_transitions():
    # Terminal state should not allow outgoing transitions
    try:
        validate_transition(PreventivoStatus.WON.value, PreventivoStatus.IN_PROGRESS.value)
    except ValueError as e:
        assert 'Invalid transition' in str(e)
    else:
        raise AssertionError("Expected ValueError for invalid transition from WON -> IN_PROGRESS")


def test_allowed_transitions_helper():
    allowed = allowed_transitions(PreventivoStatus.NEW.value)
    assert PreventivoStatus.IN_PROGRESS.value in allowed
    assert PreventivoStatus.CANCELLED.value in allowed
