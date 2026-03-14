"""
Learning Engine

Tracks fix outcomes and detects patterns over time. When users report whether
fixes worked, this engine builds correlations between symptoms, hardware,
and successful fixes so future diagnoses improve.

Three levels:
1. Direct correlation - stores (symptom, hardware, fix, outcome) tuples
2. Pattern detection - finds recurring clusters and correlations
3. Preventive recommendations - generates proactive suggestions
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class LearningEngine:
    """Learns from fix outcomes to improve future diagnoses"""

    def __init__(self, db):
        self.db = db

    def record_outcome(self, fix_id: int, issue_id: int, resolved: bool, notes: str = "") -> int:
        """
        Record whether a fix worked. This is the primary learning signal.

        Args:
            fix_id: ID of the suggested fix
            issue_id: ID of the issue
            resolved: Whether the fix resolved the issue
            notes: Optional user notes

        Returns:
            Outcome ID
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

    def detect_patterns(self):
        """
        Analyze fix history to find patterns.
        Called after each outcome recording.
        """
        try:
            self._detect_fix_effectiveness()
            self._detect_recurring_issues()
            self._detect_change_triggers()
        except Exception as e:
            logger.error(f"Pattern detection failed: {e}")

    def _detect_fix_effectiveness(self):
        """
        Track which types of fixes work best for which types of issues.
        Example: "Service restart fixes 80% of print spooler issues"
        """
        try:
            cursor = self.db.execute("""
                SELECT
                    sf.action_type,
                    i.issue_type,
                    COUNT(*) as total_attempts,
                    SUM(CASE WHEN fo.resolved = 1 THEN 1 ELSE 0 END) as successful,
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

                    # Check if pattern already exists
                    existing = self.db.execute(
                        "SELECT id FROM patterns WHERE pattern_type = 'fix_effectiveness' "
                        "AND description LIKE ?",
                        (f"%{row_dict['action_type']}%{row_dict['issue_type']}%",)
                    ).fetchone()

                    if existing:
                        self.db.execute(
                            """UPDATE patterns SET description = ?, confidence = ?,
                               times_seen = ?, last_seen = CURRENT_TIMESTAMP
                               WHERE id = ?""",
                            (description, row_dict['success_rate'],
                             row_dict['total_attempts'], existing['id'])
                        )
                    else:
                        from backend.database import Pattern
                        self.db.create_pattern(Pattern(
                            pattern_type="fix_effectiveness",
                            description=description,
                            evidence=json.dumps({
                                "action_type": row_dict['action_type'],
                                "issue_type": row_dict['issue_type']
                            }),
                            confidence=row_dict['success_rate'],
                            times_seen=row_dict['total_attempts']
                        ))

            self.db.commit()

        except Exception as e:
            logger.warning(f"Fix effectiveness detection failed: {e}")

    def _detect_recurring_issues(self):
        """
        Find issue types that keep happening.
        Example: "monitor_blackout has occurred 5 times in the last 30 days"
        """
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
                           last_seen = CURRENT_TIMESTAMP WHERE id = ?""",
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
        """
        Correlate system changes with subsequent issues.
        Example: "Issues tend to appear within 48h of NVIDIA driver updates"
        """
        try:
            # Find reliability records (installs/updates) that happened before issues
            cursor = self.db.execute("""
                SELECT
                    r.source_name,
                    r.record_type,
                    r.product_name,
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
                description = (
                    f"'{row_dict['source_name']}' changes ({row_dict['record_type']}) "
                    f"have preceded {row_dict['issue_count']} issues within 72 hours"
                )

                existing = self.db.execute(
                    "SELECT id FROM patterns WHERE pattern_type = 'change_trigger' "
                    "AND description LIKE ?",
                    (f"%{row_dict['source_name']}%",)
                ).fetchone()

                if existing:
                    self.db.execute(
                        """UPDATE patterns SET description = ?, times_seen = ?,
                           last_seen = CURRENT_TIMESTAMP WHERE id = ?""",
                        (description, row_dict['issue_count'], existing['id'])
                    )
                else:
                    from backend.database import Pattern
                    self.db.create_pattern(Pattern(
                        pattern_type="change_trigger",
                        description=description,
                        evidence=json.dumps({
                            "source": row_dict['source_name'],
                            "record_type": row_dict['record_type']
                        }),
                        confidence=min(row_dict['issue_count'] / 5.0, 1.0),
                        times_seen=row_dict['issue_count']
                    ))

            self.db.commit()

        except Exception as e:
            logger.warning(f"Change trigger detection failed: {e}")

    def get_recommendations(self) -> List[Dict[str, Any]]:
        """
        Generate preventive recommendations based on learned patterns.

        Returns:
            List of recommendation dicts
        """
        recommendations = []

        try:
            patterns = self.db.get_active_patterns()

            for pattern in patterns:
                if pattern['confidence'] < 0.3:
                    continue

                rec = {
                    "pattern_id": pattern['id'],
                    "type": pattern['pattern_type'],
                    "description": pattern['description'],
                    "confidence": pattern['confidence'],
                    "times_seen": pattern['times_seen'],
                }

                # Add specific advice based on pattern type
                if pattern['pattern_type'] == 'change_trigger':
                    rec["advice"] = (
                        "Consider creating a system restore point before "
                        "performing this type of change."
                    )
                    rec["priority"] = "high" if pattern['confidence'] > 0.6 else "medium"

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

            # Add stability-based recommendations
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
                    })
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Recommendation generation failed: {e}")

        return sorted(recommendations, key=lambda r: {"high": 0, "medium": 1, "low": 2}.get(r.get("priority", "low"), 3))
