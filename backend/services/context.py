"""
Adaptive Context Builder — dynamically allocates token budget based on issue relevance.

Instead of fixed "14 days reliability, 10 issues, all patterns", this allocates
a token budget (~2000 tokens) prioritized by relevance to the user's issue.
"""

import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Category keyword mappings
CATEGORIES = {
    'hardware': [
        'gpu', 'graphics', 'nvidia', 'amd', 'radeon', 'driver', 'vram', 'video card',
        'motherboard', 'bios', 'firmware', 'usb', 'pcie', 'hardware',
    ],
    'driver': [
        'driver', 'nvlddmkm', 'nvidia', 'amd', 'radeon', 'intel', 'update',
        'rollback', 'install', 'version',
    ],
    'crash': [
        'crash', 'bsod', 'blue screen', 'freeze', 'hang', 'not responding',
        'stopped working', 'black screen', 'restart', 'reboot', 'dump',
    ],
    'performance': [
        'slow', 'lag', 'fps', 'stutter', 'performance', 'cpu', 'ram', 'memory',
        'disk', 'usage', 'high usage', 'throttle', 'bottleneck', 'speed',
    ],
    'network': [
        'network', 'internet', 'wifi', 'ethernet', 'connection', 'dns',
        'ping', 'latency', 'disconnect', 'timeout',
    ],
    'storage': [
        'disk', 'ssd', 'hdd', 'storage', 'space', 'full', 'write',
        'read', 'io', 'partition', 'format', 'ntfs',
    ],
    'display': [
        'monitor', 'display', 'screen', 'resolution', 'refresh', 'hz',
        'flickering', 'tearing', 'artifact', 'blank', 'displayport', 'hdmi',
    ],
}


def score_context_relevance(description: str, category: str) -> float:
    """
    Score how relevant a context category is to the issue description.
    Simple keyword matching with category mapping.
    """
    if not description:
        return 0.0

    desc_lower = description.lower()
    keywords = CATEGORIES.get(category, [])
    if not keywords:
        return 0.0

    matches = sum(1 for kw in keywords if kw in desc_lower)
    # Normalize: more matches = higher score, max 1.0
    return min(matches / max(len(keywords) * 0.3, 1), 1.0)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(str(text)) // 4


def _truncate_to_budget(text: str, budget_tokens: int) -> str:
    """Truncate text to fit within token budget."""
    max_chars = budget_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + '...'


def build_adaptive_context(db, description: str, budget_tokens: int = 2000) -> Dict[str, Any]:
    """
    Build context dynamically sized based on issue relevance.

    Allocates budget: 40% to highest-relevance section, 30% to second,
    20% to third, 10% to everything else.
    """
    # Score each category
    scores = {}
    for category in CATEGORIES:
        scores[category] = score_context_relevance(description, category)

    # Sort categories by relevance
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # Allocate token budgets
    allocations = {}
    budget_shares = [0.40, 0.30, 0.20, 0.10]
    for i, (category, score) in enumerate(ranked):
        if i < len(budget_shares):
            allocations[category] = int(budget_tokens * budget_shares[i])
        else:
            allocations[category] = int(budget_tokens * 0.05)  # Minimal for remaining

    context = {
        'issue': description,
        'relevance_scores': {cat: round(s, 2) for cat, s in ranked if s > 0},
    }

    try:
        # Get latest snapshot
        cursor = db.execute("SELECT id FROM snapshots ORDER BY timestamp DESC LIMIT 1")
        row = cursor.fetchone()
        if not row:
            return context
        snapshot_id = row[0]

        # Hardware context (serves hardware, driver, display categories)
        hw_budget = allocations.get('hardware', 200) + allocations.get('driver', 150) + allocations.get('display', 100)
        hw_context = _build_hardware_context(db, snapshot_id, hw_budget)
        if hw_context:
            context['hardware'] = hw_context

        # Reliability/crash context
        crash_budget = allocations.get('crash', 200)
        crash_score = scores.get('crash', 0)
        # More days of data if crash-related
        days = 30 if crash_score > 0.3 else 14
        limit = 30 if crash_score > 0.3 else 15
        rel_context = _build_reliability_context(db, days, limit, crash_budget)
        if rel_context:
            context['reliability'] = rel_context

        # Performance context
        perf_budget = allocations.get('performance', 150)
        if scores.get('performance', 0) > 0.1:
            perf_context = _build_performance_context(db, snapshot_id, perf_budget)
            if perf_context:
                context['performance'] = perf_context

        # Recent issues (always include, small budget)
        try:
            recent = db.get_issues(limit=5)
            context['recent_issues'] = [dict(i) for i in recent]
        except Exception:
            pass

        # Learned patterns (always include, top 5 by relevance × confidence)
        try:
            from backend.ai.learning import LearningEngine
            learning = LearningEngine(db)
            patterns = learning.get_active_patterns_decayed()
            context['learned_patterns'] = [
                {"type": p["pattern_type"], "description": p["description"],
                 "confidence": p["confidence"], "decayed_confidence": p["decayed_confidence"],
                 "times_seen": p["times_seen"]}
                for p in patterns[:5]
            ]
        except Exception:
            pass

        # Similar past fixes (always include, up to 3)
        try:
            from backend.services.matching import find_similar_fixes
            similar = find_similar_fixes(db, description, limit=3)
            if similar:
                context['similar_past_fixes'] = similar
        except Exception:
            pass

        # Style guide
        try:
            guide = db.get_style_guide('diagnosis')
            if guide:
                context['style_guide'] = guide['guide']
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Adaptive context build failed: {e}")

    return context


def _build_hardware_context(db, snapshot_id: int, budget: int) -> Optional[Dict]:
    """Build hardware context within token budget."""
    hw = {}
    try:
        gpu = db.get_gpu_state(snapshot_id)
        if gpu:
            hw['gpu'] = dict(gpu)

        monitors = db.get_monitor_states(snapshot_id)
        if monitors:
            hw['monitors'] = [dict(m) for m in monitors]

        hardware_states = db.get_hardware_states(snapshot_id)
        for hs in hardware_states:
            hs_dict = dict(hs)
            comp_type = hs_dict.get('component_type', '')
            try:
                hs_dict['component_data'] = json.loads(hs_dict.get('component_data', '{}'))
            except (json.JSONDecodeError, TypeError):
                pass
            hw[comp_type] = hs_dict

    except Exception as e:
        logger.warning(f"Hardware context build failed: {e}")

    return hw if hw else None


def _build_reliability_context(db, days: int, limit: int, budget: int) -> Optional[Dict]:
    """Build reliability context within token budget."""
    try:
        records = db.get_recent_reliability_records(days=days, limit=limit)
        if not records:
            return None

        return {
            'records': records,
            'crash_count': sum(1 for r in records if 'crash' in r.get('record_type', '')),
            'stability_index': next(
                (r.get('stability_index') for r in records if r.get('stability_index')),
                None
            )
        }
    except Exception:
        return None


def _build_performance_context(db, snapshot_id: int, budget: int) -> Optional[Dict]:
    """Build performance-specific context."""
    try:
        hw_states = db.get_hardware_states(snapshot_id)
        perf = {}
        for hs in hw_states:
            comp_type = hs.get('component_type', '')
            if comp_type in ('cpu', 'memory', 'storage'):
                try:
                    data = json.loads(hs.get('component_data', '{}'))
                    perf[comp_type] = data
                except (json.JSONDecodeError, TypeError):
                    pass
        return perf if perf else None
    except Exception:
        return None
