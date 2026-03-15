"""
Learning Engine

Tracks fix outcomes and detects patterns over time. When users report whether
fixes worked, this engine builds correlations between symptoms, hardware,
and successful fixes so future diagnoses improve.

Features:
- Direct correlation: stores (symptom, hardware, fix, outcome) tuples
- Pattern detection: finds recurring clusters and correlations
- Confidence decay: patterns lose relevance over time (H3-inspired exponential decay)
- Preventive recommendations: generates proactive suggestions with decayed confidence
"""

import json
import hashlib
import logging
import math
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Confidence decay: half-life of 30 days
DECAY_HALF_LIFE_DAYS = 30
DECAY_THRESHOLD = 0.1  # Below this, patterns are pruned from context


class LearningEngine:
    """Learns from fix outcomes to improve future diagnoses"""

    def __init__(self, db):
        self.db = db

    # ========================================================================
    # Confidence Decay (H3-inspired)
    # ========================================================================

    @staticmethod
    def get_decayed_confidence(pattern: Dict[str, Any]) -> float:
        """
        Calculate effective confidence with exponential decay.
        Formula: effective = stored_confidence * 0.5^(days_since_activity / 30)
        """
        stored = pattern.get('confidence', 0.0)
        last_activity = pattern.get('last_activity_at') or pattern.get('last_seen')
        if not last_activity or stored <= 0:
            return stored

        try:
            last_dt = datetime.fromisoformat(last_activity.replace('Z', '+00:00')) if 'T' in last_activity else datetime.strptime(last_activity, '%Y-%m-%d %H:%M:%S')
            days_since = (datetime.now() - last_dt.replace(tzinfo=None)).total_seconds() / 86400
            if days_since <= 0:
                return stored
            decayed = stored * math.pow(0.5, days_since / DECAY_HALF_LIFE_DAYS)
            return round(decayed, 4)
        except Exception:
            return stored

    def get_active_patterns_decayed(self, pattern_type: str = None) -> List[Dict[str, Any]]:
        """Get active patterns with decayed confidence values, sorted by relevance."""
        patterns = self.db.get_active_patterns(pattern_type)
        result = []
        for p in patterns:
            p = dict(p)
            p['decayed_confidence'] = self.get_decayed_confidence(p)
            if p['decayed_confidence'] >= DECAY_THRESHOLD:
                result.append(p)
        result.sort(key=lambda x: x['decayed_confidence'], reverse=True)
        return result

    # ========================================================================
    # Confidence Adjustment on Fix Transitions
    # ========================================================================

    def boost_pattern_confidence(self, pattern_id: int, amount: float = 0.1):
        """Boost a pattern's confidence (capped at 1.0) when a fix is verified."""
        try:
            cursor = self.db.execute("SELECT confidence FROM patterns WHERE id = ?", (pattern_id,))
            row = cursor.fetchone()
            if row:
                new_conf = min(1.0, row['confidence'] + amount)
                self.db.execute(
                    "UPDATE patterns SET confidence = ?, last_activity_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (new_conf, pattern_id)
                )
                self.db.commit()
        except Exception as e:
            logger.warning(f"Failed to boost pattern {pattern_id}: {e}")

    def decrease_pattern_confidence(self, pattern_id: int, amount: float = 0.05):
        """Decrease a pattern's confidence when a fix fails or is reverted."""
        try:
            cursor = self.db.execute("SELECT confidence FROM patterns WHERE id = ?", (pattern_id,))
            row = cursor.fetchone()
            if row:
                new_conf = max(0.0, row['confidence'] - amount)
                self.db.execute(
                    "UPDATE patterns SET confidence = ?, last_activity_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (new_conf, pattern_id)
                )
                self.db.commit()
        except Exception as e:
            logger.warning(f"Failed to decrease pattern {pattern_id}: {e}")

    # ========================================================================
    # Outcome Recording
    # ========================================================================

    def record_outcome(self, fix_id: int, issue_id: int, resolved: bool, notes: str = "") -> int:
        """
        Record whether a fix worked. This is the primary learning signal.
        """
        from backend.database import FixOutcome

        outcome = FixOutcome(
            fix_id=fix_id,
            issue_id=issue_id,
            resolved=resolved,
            user_notes=notes
        )
        outcome_id = self.db.create_fix_outcome(outcome)

        # Update issue status if resolved
        if resolved:
            self.db.execute(
                "UPDATE issues SET severity = 'low' WHERE id = ?",
                (issue_id,)
            )
            self.db.commit()

        # Trigger pattern recomputation
        self.detect_patterns()

        logger.info(f"Recorded outcome for fix {fix_id}: {'resolved' if resolved else 'not resolved'}")
        return outcome_id

    # ========================================================================
    # Pattern Detection
    # ========================================================================

    def detect_patterns(self):
        """Analyze fix history to find patterns. Called after each outcome recording."""
        try:
            self._detect_fix_effectiveness()
            self._detect_recurring_issues()
            self._detect_change_triggers()
        except Exception as e:
            logger.error(f"Pattern detection failed: {e}")

    def _get_hardware_config_hash(self) -> Optional[str]:
        """Build a hash of the current hardware config for pattern correlation."""
        try:
            cursor = self.db.execute("SELECT id FROM snapshots ORDER BY timestamp DESC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                return None
            snapshot_id = row[0]
            gpu = self.db.get_gpu_state(snapshot_id)
            parts = []
            if gpu:
                parts.append(f"gpu:{gpu.get('gpu_name', '')}")
                parts.append(f"driver:{gpu.get('driver_version', '')}")
            # Add OS info if available
            hw_states = self.db.get_hardware_states(snapshot_id)
            for hw in hw_states:
                if hw.get('component_type') == 'os':
                    parts.append(f"os:{hw.get('component_data', '')[:50]}")
            if parts:
                return hashlib.md5('|'.join(parts).encode()).hexdigest()[:12]
        except Exception:
            pass
        return None

    def _detect_fix_effectiveness(self):
        """Track which types of fixes work best for which types of issues."""
        try:
            hw_hash = self._get_hardware_config_hash()
            cursor = self.db.execute("""
                SELECT
                    sf.action_type,
                    i.issue_type,
                    COUNT(*) as total_attempts,
                    SUM(CASE WHEN fo.resolved = 1 THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN fo.resolved = 0 THEN 1 ELSE 0 END) as failed,
                    AVG(CASE WHEN fo.resolved = 1 THEN 1.0 ELSE 0.0 END) as success_rate
                FROM fix_outcomes fo
                JOIN suggested_fixes sf ON fo.fix_id = sf.id
                JOIN issues i ON fo.issue_id = i.id
                GROUP BY sf.action_type, i.issue_type
                HAVING total_attempts >= 2
            """)

            for row in cursor.fetchall():
                row_dict = dict(row)
                if row_dict['success_rate'] > 0:
                    description = (
                        f"'{row_dict['action_type']}' fixes resolve "
                        f"'{row_dict['issue_type']}' issues "
                        f"{int(row_dict['success_rate'] * 100)}% of the time "
                        f"({row_dict['total_attempts']} attempts)"
                    )

                    evidence = {
                        "action_type": row_dict['action_type'],
                        "issue_type": row_dict['issue_type'],
                    }
                    if hw_hash:
                        evidence["hardware_config_hash"] = hw_hash

                    existing = self.db.execute(
                        "SELECT id FROM patterns WHERE pattern_type = 'fix_effectiveness' "
                        "AND description LIKE ?",
                        (f"%{row_dict['action_type']}%{row_dict['issue_type']}%",)
                    ).fetchone()

                    if existing:
                        self.db.execute(
                            """UPDATE patterns SET description = ?, confidence = ?,
                               times_seen = ?, times_failed = ?,
                               last_seen = CURRENT_TIMESTAMP, last_activity_at = CURRENT_TIMESTAMP
                               WHERE id = ?""",
                            (description, row_dict['success_rate'],
                             row_dict['successful'], row_dict['failed'], existing['id'])
                        )
                    else:
                        from backend.database import Pattern
                        self.db.create_pattern(Pattern(
                            pattern_type="fix_effectiveness",
                            description=description,
                            evidence=json.dumps(evidence),
                            confidence=row_dict['success_rate'],
                            times_seen=row_dict['successful'],
                            times_failed=row_dict['failed'],
                        ))

            self.db.commit()

        except Exception as e:
            logger.warning(f"Fix effectiveness detection failed: {e}")

    def _detect_recurring_issues(self):
        """Find issue types that keep happening."""
        try:
            cursor = self.db.execute("""
                SELECT issue_type, COUNT(*) as count
                FROM issues
                WHERE timestamp >= datetime('now', '-30 days')
                GROUP BY issue_type
                HAVING count >= 3
            """)

            for row in cursor.fetchall():
                row_dict = dict(row)
                description = (
                    f"'{row_dict['issue_type']}' has occurred "
                    f"{row_dict['count']} times in the last 30 days"
                )

                existing = self.db.execute(
                    "SELECT id FROM patterns WHERE pattern_type = 'recurring_issue' "
                    "AND description LIKE ?",
                    (f"%{row_dict['issue_type']}%",)
                ).fetchone()

                if existing:
                    self.db.execute(
                        """UPDATE patterns SET description = ?, times_seen = ?,
                           last_seen = CURRENT_TIMESTAMP, last_activity_at = CURRENT_TIMESTAMP WHERE id = ?""",
                        (description, row_dict['count'], existing['id'])
                    )
                else:
                    from backend.database import Pattern
                    self.db.create_pattern(Pattern(
                        pattern_type="recurring_issue",
                        description=description,
                        evidence=json.dumps({"issue_type": row_dict['issue_type']}),
                        confidence=min(row_dict['count'] / 10.0, 1.0),
                        times_seen=row_dict['count']
                    ))

            self.db.commit()

        except Exception as e:
            logger.warning(f"Recurring issue detection failed: {e}")

    def _detect_change_triggers(self):
        """Correlate system changes with subsequent issues."""
        try:
            cursor = self.db.execute("""
                SELECT
                    r.source_name,
                    r.record_type,
                    r.product_name,
                    r.event_message,
                    COUNT(DISTINCT i.id) as issue_count
                FROM reliability_records r
                JOIN issues i ON
                    i.timestamp >= r.event_time
                    AND i.timestamp <= datetime(r.event_time, '+72 hours')
                WHERE r.record_type IN ('app_install', 'os_update', 'driver_install')
                GROUP BY r.source_name, r.record_type
                HAVING issue_count >= 2
            """)

            for row in cursor.fetchall():
                row_dict = dict(row)
                # Include the specific trigger event detail
                trigger_detail = row_dict.get('event_message', '') or row_dict.get('product_name', '')
                description = (
                    f"'{row_dict['source_name']}' changes ({row_dict['record_type']}) "
                    f"have preceded {row_dict['issue_count']} issues within 72 hours"
                )

                evidence = {
                    "source": row_dict['source_name'],
                    "record_type": row_dict['record_type'],
                }
                if trigger_detail:
                    evidence["trigger_detail"] = trigger_detail[:200]

                existing = self.db.execute(
                    "SELECT id FROM patterns WHERE pattern_type = 'change_trigger' "
                    "AND description LIKE ?",
                    (f"%{row_dict['source_name']}%",)
                ).fetchone()

                if existing:
                    self.db.execute(
                        """UPDATE patterns SET description = ?, times_seen = ?,
                           evidence = ?,
                           last_seen = CURRENT_TIMESTAMP, last_activity_at = CURRENT_TIMESTAMP WHERE id = ?""",
                        (description, row_dict['issue_count'], json.dumps(evidence), existing['id'])
                    )
                else:
                    from backend.database import Pattern
                    self.db.create_pattern(Pattern(
                        pattern_type="change_trigger",
                        description=description,
                        evidence=json.dumps(evidence),
                        confidence=min(row_dict['issue_count'] / 5.0, 1.0),
                        times_seen=row_dict['issue_count']
                    ))

            self.db.commit()

        except Exception as e:
            logger.warning(f"Change trigger detection failed: {e}")

    # ========================================================================
    # Recommendations (with decay)
    # ========================================================================

    def get_recommendations(self) -> List[Dict[str, Any]]:
        """Generate preventive recommendations using decayed confidence."""
        recommendations = []

        try:
            patterns = self.get_active_patterns_decayed()

            for pattern in patterns:
                decayed = pattern['decayed_confidence']
                if decayed < 0.3:
                    continue

                rec = {
                    "pattern_id": pattern['id'],
                    "type": pattern['pattern_type'],
                    "description": pattern['description'],
                    "confidence": pattern['confidence'],
                    "decayed_confidence": decayed,
                    "times_seen": pattern['times_seen'],
                    "times_failed": pattern.get('times_failed', 0),
                }

                if pattern['pattern_type'] == 'change_trigger':
                    rec["advice"] = (
                        "Consider creating a system restore point before "
                        "performing this type of change."
                    )
                    rec["priority"] = "high" if decayed > 0.6 else "medium"
                elif pattern['pattern_type'] == 'recurring_issue':
                    rec["advice"] = (
                        "This issue keeps happening. Consider investigating "
                        "the root cause rather than applying quick fixes."
                    )
                    rec["priority"] = "high"
                elif pattern['pattern_type'] == 'fix_effectiveness':
                    rec["advice"] = (
                        "This fix type has a track record for this issue type. "
                        "Try it first next time."
                    )
                    rec["priority"] = "low"

                recommendations.append(rec)

            # Stability-based recommendations
            try:
                stability = self.db.execute(
                    """SELECT stability_index FROM reliability_records
                       WHERE stability_index IS NOT NULL
                       ORDER BY event_time DESC LIMIT 1"""
                ).fetchone()

                if stability and stability['stability_index'] < 5.0:
                    recommendations.append({
                        "type": "stability_warning",
                        "description": f"System stability index is {stability['stability_index']:.1f}/10",
                        "advice": (
                            "Your system stability is below average. Consider: "
                            "1) Creating a backup, "
                            "2) Checking for pending Windows updates, "
                            "3) Updating drivers to stable (not beta) versions."
                        ),
                        "priority": "high",
                        "confidence": 1.0,
                        "decayed_confidence": 1.0,
                    })
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Recommendation generation failed: {e}")

        return sorted(recommendations, key=lambda r: {"high": 0, "medium": 1, "low": 2}.get(r.get("priority", "low"), 3))
