"""
Fix Service - approve, reject, execute, and record fix outcomes.
Uses state machine for validated transitions and holding period for verification.
"""

import subprocess
import logging
from datetime import datetime, timedelta

from backend.ai.learning import LearningEngine
from backend.services.state_machine import transition, can_transition, get_valid_events
from backend.services.events import emit_fix_status

logger = logging.getLogger(__name__)

# Holding period before auto-resolving (hours)
HOLDING_PERIOD_HOURS = 24


def approve_fix(db, fix_id):
    """Approve a pending fix. Returns dict or error string."""
    fix = db.get_fix(fix_id)
    if not fix:
        return None, 'Fix not found'

    old_state = fix['status']
    new_state, ok = transition(old_state, 'APPROVE')
    if not ok:
        return None, f'Cannot approve: fix is "{old_state}". Valid actions: {get_valid_events(old_state)}'

    db.update_fix_status(fix_id, new_state)
    emit_fix_status(fix_id, old_state, new_state, 'APPROVE')
    return {'status': new_state, 'fix_id': fix_id}, None


def reject_fix(db, fix_id):
    """Reject a fix. Returns dict or error string."""
    fix = db.get_fix(fix_id)
    if not fix:
        return None, 'Fix not found'

    old_state = fix['status']
    new_state, ok = transition(old_state, 'REJECT')
    if not ok:
        return None, f'Cannot reject: fix is "{old_state}". Valid actions: {get_valid_events(old_state)}'

    db.update_fix_status(fix_id, new_state)
    emit_fix_status(fix_id, old_state, new_state, 'REJECT')
    return {'status': new_state, 'fix_id': fix_id}, None


def execute_fix(db, fix_id):
    """Execute an approved fix. Returns result dict or error."""
    fix = db.get_fix(fix_id)
    if not fix:
        return None, 'Fix not found'

    old_state = fix['status']
    new_state, ok = transition(old_state, 'EXECUTE')
    if not ok:
        return None, f'Cannot execute: fix is "{old_state}". Valid actions: {get_valid_events(old_state)}'

    action_type = fix.get('action_type', '')
    action_detail = fix.get('action_detail', '')
    output = ""
    success = True

    if action_type == 'command':
        try:
            result = subprocess.run(
                ["powershell.exe", "-Command", action_detail],
                capture_output=True, text=True, timeout=60
            )
            output = result.stdout + result.stderr
            success = result.returncode == 0
        except subprocess.TimeoutExpired:
            output = "Command timed out after 60 seconds"
            success = False
        except Exception as e:
            output = f"Execution error: {e}"
            success = False

    elif action_type == 'service':
        try:
            result = subprocess.run(
                ["powershell.exe", "-Command", f"Restart-Service -Name '{action_detail}' -Force"],
                capture_output=True, text=True, timeout=30
            )
            output = result.stdout + result.stderr
            success = result.returncode == 0
        except Exception as e:
            output = f"Service restart error: {e}"
            success = False

    elif action_type == 'manual':
        output = "Manual fix - user will follow the instructions"
    else:
        output = f"Action type '{action_type}' - user should follow instructions"

    db.update_fix_status(fix_id, new_state, output=output, success=success)
    emit_fix_status(fix_id, old_state, new_state, 'EXECUTE')

    return {
        'status': new_state,
        'fix_id': fix_id,
        'success': success,
        'output': output,
    }, None


def record_outcome(db, fix_id, resolved, notes=''):
    """
    Record whether a fix resolved the issue.
    If resolved: enter holding state for verification period.
    If not: mark as failed and decrease pattern confidence.
    """
    fix = db.get_fix(fix_id)
    if not fix:
        return None, 'Fix not found'

    learning = LearningEngine(db)

    if resolved:
        # Transition to holding state for verification
        new_state, ok = transition(fix['status'], 'VERIFY')
        if ok:
            holding_since = datetime.now().isoformat()
            auto_verify_at = (datetime.now() + timedelta(hours=HOLDING_PERIOD_HOURS)).isoformat()
            db.execute(
                "UPDATE suggested_fixes SET status = ?, holding_since = ?, auto_verify_at = ? WHERE id = ?",
                (new_state, holding_since, auto_verify_at, fix_id)
            )
            db.commit()
        else:
            # Fallback: just mark as executed if transition not valid from current state
            logger.warning(f"Cannot enter holding from {fix['status']}, recording outcome directly")
    else:
        # Transition to failed
        new_state, ok = transition(fix['status'], 'FAIL')
        if ok:
            db.update_fix_status(fix_id, new_state)

        # Decrease confidence for related patterns
        patterns = learning.get_active_patterns_decayed('fix_effectiveness')
        for p in patterns:
            if fix.get('action_type') and fix['action_type'] in p.get('description', ''):
                learning.decrease_pattern_confidence(p['id'], 0.05)
                break

    # Record the outcome
    outcome_id = learning.record_outcome(
        fix_id=fix_id,
        issue_id=fix['issue_id'],
        resolved=resolved,
        notes=notes,
    )

    current_fix = db.get_fix(fix_id)
    return {
        'status': 'recorded',
        'outcome_id': outcome_id,
        'resolved': resolved,
        'fix_status': current_fix['status'] if current_fix else 'unknown',
        'holding_period': f'{HOLDING_PERIOD_HOURS}h' if resolved else None,
    }, None
