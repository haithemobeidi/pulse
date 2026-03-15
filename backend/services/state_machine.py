"""
Fix State Machine — tracks fix lifecycle through defined transitions.

States: pending → approved → executed → holding → resolved | failed
Events: APPROVE, REJECT, EXECUTE, VERIFY, REVERT, RETRY, FAIL

Inspired by H3's defineStateMachine pattern, implemented as pure Python.
"""

import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Valid state transitions: {current_state: {event: next_state}}
TRANSITIONS = {
    'pending': {
        'APPROVE': 'approved',
        'REJECT': 'rejected',
    },
    'approved': {
        'EXECUTE': 'executed',
        'REJECT': 'rejected',
    },
    'executed': {
        'VERIFY': 'holding',
        'FAIL': 'failed',
        'REVERT': 'rolled_back',
    },
    'holding': {
        'RESOLVE': 'resolved',
        'REVERT': 'executed',
        'FAIL': 'failed',
    },
    'resolved': {
        'REVERT': 'executed',
    },
    'failed': {
        'RETRY': 'pending',
    },
    'rejected': {},
    'rolled_back': {
        'RETRY': 'pending',
    },
}


def can_transition(current_state: str, event: str) -> bool:
    """Check if a transition is valid."""
    return event in TRANSITIONS.get(current_state, {})


def get_next_state(current_state: str, event: str) -> Optional[str]:
    """Get the next state for a given event, or None if invalid."""
    return TRANSITIONS.get(current_state, {}).get(event)


def transition(current_state: str, event: str) -> Tuple[str, bool]:
    """
    Attempt a state transition.
    Returns (new_state, success). If invalid, returns (current_state, False).
    """
    next_state = get_next_state(current_state, event)
    if next_state is None:
        logger.warning(f"Invalid transition: {current_state} + {event}")
        return current_state, False
    logger.info(f"State transition: {current_state} → {next_state} (event: {event})")
    return next_state, True


def get_valid_events(current_state: str) -> list:
    """Get all valid events for a given state."""
    return list(TRANSITIONS.get(current_state, {}).keys())
