"""
Analysis Service - AI-powered issue analysis with context building.
"""

import json
import logging

from backend.database import Snapshot, SnapshotType, Issue, IssueType, IssueSeverity, AiAnalysis, SuggestedFix
from backend.ai.reasoning import analyze_issue as ai_analyze, build_context
from backend.services.collection import run_collection
from backend.services.screenshots import save_screenshot

logger = logging.getLogger(__name__)


def to_str(v):
    """Convert value to string, joining lists."""
    if isinstance(v, list):
        return '\n'.join(str(i) for i in v)
    return str(v) if v is not None else ''


def to_float(v):
    """Convert value to float, handling lists."""
    if isinstance(v, list):
        v = v[0] if v else 0.5
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.5


def _build_recent_context(db):
    """Build recent system events context string for AI."""
    context = ""
    try:
        recent_records = db.get_recent_reliability_records(days=1, limit=20)
        recent_issues = db.execute(
            "SELECT * FROM issues ORDER BY timestamp DESC LIMIT 10"
        ).fetchall()
        if recent_records:
            context += "\n\nRecent system events (last 24h):\n"
            for r in recent_records[:15]:
                context += f"- [{r.get('event_time', '')}] {r.get('record_type', '')}: {r.get('source_name', '')} - {(r.get('event_message', '') or '')[:150]}\n"
        if recent_issues:
            context += "\nRecent issues:\n"
            for iss in recent_issues[:5]:
                context += f"- [{iss['timestamp']}] {iss['issue_type']}: {iss['description'][:150]}\n"
    except Exception as e:
        logger.warning(f"Failed to build recent context: {e}")
    return context


def run_analysis(db, description, screenshot_data=None, provider='auto', include_context=False):
    """
    Full analysis flow: collect data, run AI analysis, store results.
    Returns analysis dict with issue_id, snapshot_id, analysis_id, suggested_fixes.
    """
    from backend.services.events import emit_analysis_progress

    # Save screenshot if provided
    screenshot_path = save_screenshot(screenshot_data)

    # Build context
    emit_analysis_progress('context', 'running', 'Building context...')
    full_description = description
    if include_context:
        recent_context = _build_recent_context(db)
        if recent_context:
            full_description += recent_context

    # Collect fresh system data
    emit_analysis_progress('collecting', 'running', 'Scanning system...')
    collection = run_collection(
        db,
        snapshot_type=SnapshotType.ISSUE_LOGGED,
        notes=f"AI Analysis: {description[:100]}",
        days=14,
        timeout=30,
    )
    snapshot_id = collection['snapshot_id']

    # Log the issue
    issue = Issue(
        snapshot_id=snapshot_id,
        issue_type=IssueType.OTHER,
        description=description,
        severity=IssueSeverity.MEDIUM,
    )
    issue_id = db.create_issue(issue)

    # Run AI analysis
    emit_analysis_progress('analyzing', 'running', 'AI analyzing...')
    analysis = ai_analyze(db, full_description, screenshot_path, provider)

    # Store analysis in database
    emit_analysis_progress('storing', 'running', 'Saving results...')
    ai_record = AiAnalysis(
        issue_id=issue_id,
        diagnosis=analysis.get('diagnosis', ''),
        confidence=analysis.get('confidence', 0),
        root_cause=analysis.get('root_cause', ''),
        raw_response=json.dumps(analysis),
        model_used=analysis.get('model', 'unknown'),
        tokens_input=analysis.get('tokens_used', {}).get('input', 0),
        tokens_output=analysis.get('tokens_used', {}).get('output', 0),
    )
    analysis_id = db.create_ai_analysis(ai_record)

    # Store suggested fixes
    stored_fixes = []
    for fix_data in analysis.get('suggested_fixes', []):
        fix = SuggestedFix(
            analysis_id=analysis_id,
            issue_id=issue_id,
            title=to_str(fix_data.get('title', '')),
            description=to_str(fix_data.get('description', '')),
            risk_level=to_str(fix_data.get('risk_level', 'medium')),
            action_type=to_str(fix_data.get('action_type', 'manual')),
            action_detail=to_str(fix_data.get('action_detail', '')),
            estimated_success=to_float(fix_data.get('estimated_success', 0.5)),
            reversible=bool(fix_data.get('reversible', True)),
            status='pending',
        )
        fix_id = db.create_suggested_fix(fix)
        fix_data['id'] = fix_id
        stored_fixes.append(fix_data)

    analysis['suggested_fixes'] = stored_fixes
    analysis['issue_id'] = issue_id
    analysis['snapshot_id'] = snapshot_id
    analysis['analysis_id'] = analysis_id

    emit_analysis_progress('complete', 'done', 'Analysis complete')

    # Embed the issue and fixes for future similarity matching (non-blocking)
    try:
        from backend.services.embeddings import embed_and_store
        embed_and_store(db, 'issue', issue_id, description)
        for fix_data in stored_fixes:
            if fix_data.get('id'):
                fix_text = f"{fix_data.get('title', '')} {fix_data.get('description', '')}"
                embed_and_store(db, 'fix', fix_data['id'], fix_text)
    except Exception as e:
        logger.warning(f"Embedding failed (non-critical): {e}")

    return analysis
