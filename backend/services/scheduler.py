"""
Background Scheduler — lightweight periodic jobs using threading.Timer.

Jobs:
- Verify fixes in 'holding' state past their auto_verify_at time → transition to 'resolved'
- No external dependencies (no APScheduler needed)
"""

import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

_timer = None
_running = False
CHECK_INTERVAL_SECONDS = 3600  # Check every hour


def _check_holding_fixes(db):
    """Check fixes in holding state and auto-resolve if past verification time."""
    try:
        fixes = db.get_fixes_in_holding()
        now = datetime.now().isoformat()

        for fix in fixes:
            auto_verify = fix.get('auto_verify_at')
            if auto_verify and auto_verify <= now:
                # Auto-transition to resolved
                from backend.services.state_machine import transition
                new_state, ok = transition(fix['status'], 'RESOLVE')
                if ok:
                    db.execute(
                        "UPDATE suggested_fixes SET status = ? WHERE id = ?",
                        (new_state, fix['id'])
                    )
                    db.commit()

                    # Boost related pattern confidence
                    try:
                        from backend.ai.learning import LearningEngine
                        learning = LearningEngine(db)
                        # Find related patterns
                        patterns = learning.get_active_patterns_decayed('fix_effectiveness')
                        for p in patterns:
                            if fix.get('action_type') and fix['action_type'] in p.get('description', ''):
                                learning.boost_pattern_confidence(p['id'], 0.1)
                                break
                    except Exception as e:
                        logger.debug(f"Pattern boost on auto-resolve failed: {e}")

                    logger.info(f"Fix {fix['id']} auto-resolved after holding period")

    except Exception as e:
        logger.error(f"Holding fix check failed: {e}")


def _run_periodic(db):
    """Periodic job runner."""
    global _timer, _running
    if not _running:
        return

    _check_holding_fixes(db)

    # Schedule next run
    _timer = threading.Timer(CHECK_INTERVAL_SECONDS, _run_periodic, args=[db])
    _timer.daemon = True
    _timer.start()


def start_scheduler(db):
    """Start the background scheduler."""
    global _running, _timer
    if _running:
        return

    _running = True
    logger.info(f"Background scheduler started (interval: {CHECK_INTERVAL_SECONDS}s)")

    # Run first check after a short delay
    _timer = threading.Timer(10, _run_periodic, args=[db])
    _timer.daemon = True
    _timer.start()


def stop_scheduler():
    """Stop the background scheduler."""
    global _running, _timer
    _running = False
    if _timer:
        _timer.cancel()
        _timer = None
    logger.info("Background scheduler stopped")
