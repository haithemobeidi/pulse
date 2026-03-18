"""
Living Brain Service — OpenClaw-inspired learning system for Pulse.

The brain gets smarter over time by tracking troubleshooting outcomes.
For API-based models, learning = building better context from evidence.

Core loop:
  User reports problem → AI diagnoses → User tries fix → User reports outcome
  → Brain extracts facts → Updates confidence → Next time, better context

Key components:
  - Troubleshooting facts with outcome-based confidence
  - Fact relations (causes, resolves, co-occurs)
  - Session outcome tracking
  - Knowledge gap detection
  - Smart context assembly (ranked by confidence + decay)
"""

import json
import math
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Decay half-life in days
DECAY_HALF_LIFE = 30
# Minimum confidence to include a fact in context
MIN_CONFIDENCE_FOR_CONTEXT = 0.15
# Max facts to inject into prompt
MAX_FACTS_IN_CONTEXT = 8
# Max knowledge gaps to inject
MAX_GAPS_IN_CONTEXT = 3


# ============================================================================
# Confidence & Decay
# ============================================================================

def calculate_confidence(success_count: int, failure_count: int) -> float:
    """Calculate confidence from outcomes. Uses Laplace smoothing to avoid 0/0."""
    total = success_count + failure_count
    if total == 0:
        return 0.5  # No data = neutral
    # Laplace smoothing: (successes + 1) / (total + 2)
    return (success_count + 1) / (total + 2)


def calculate_decay(last_accessed: str, half_life: int = DECAY_HALF_LIFE) -> float:
    """Exponential decay based on time since last access."""
    if not last_accessed:
        return 0.5
    try:
        if 'T' in last_accessed:
            last_dt = datetime.fromisoformat(last_accessed.replace('Z', '+00:00')).replace(tzinfo=None)
        else:
            last_dt = datetime.strptime(last_accessed, '%Y-%m-%d %H:%M:%S')
        age_days = (datetime.now() - last_dt).total_seconds() / 86400
        if age_days <= 0:
            return 1.0
        lambda_val = math.log(2) / half_life
        return math.exp(-lambda_val * age_days)
    except Exception:
        return 0.5


def get_activation_tier(last_accessed: str) -> str:
    """Determine activation tier based on recency."""
    if not last_accessed:
        return 'cool'
    try:
        if 'T' in last_accessed:
            last_dt = datetime.fromisoformat(last_accessed.replace('Z', '+00:00')).replace(tzinfo=None)
        else:
            last_dt = datetime.strptime(last_accessed, '%Y-%m-%d %H:%M:%S')
        days = (datetime.now() - last_dt).days
        if days <= 7:
            return 'hot'
        elif days <= 30:
            return 'warm'
        return 'cool'
    except Exception:
        return 'warm'


# ============================================================================
# Fact Management
# ============================================================================

def record_fact(db, symptom: str, diagnosis: str = None, resolution: str = None,
                worked: bool = None, hardware_context: dict = None,
                source: str = 'session') -> int:
    """
    Record a troubleshooting fact. If a similar fact exists, update it.
    Returns the fact ID.
    """
    hw_json = json.dumps(hardware_context) if hardware_context else None

    # Search for existing similar fact
    existing = find_similar_fact(db, symptom, diagnosis, resolution)
    if existing:
        fact_id = existing['id']
        if worked is not None:
            db.update_fact_outcome(fact_id, worked)
        logger.info(f"Updated existing fact {fact_id}: {symptom[:50]}")
        return fact_id

    # Create new fact
    confidence = 0.5
    fact_id = db.create_fact(
        symptom=symptom,
        diagnosis=diagnosis,
        resolution=resolution,
        confidence=confidence,
        hardware_context=hw_json,
        source=source,
    )

    # Set initial outcome if known
    if worked is not None:
        db.update_fact_outcome(fact_id, worked)

    logger.info(f"Created new fact {fact_id}: {symptom[:50]}")
    return fact_id


def find_similar_fact(db, symptom: str, diagnosis: str = None,
                      resolution: str = None) -> Optional[Dict[str, Any]]:
    """
    Find an existing fact that's similar enough to be the same knowledge.
    Uses keyword overlap for now (vector similarity in Phase 2D).
    """
    # Get candidate facts matching key symptom words
    symptom_words = set(symptom.lower().split())
    symptom_words -= {'the', 'a', 'an', 'is', 'my', 'it', 'i', 'in', 'on', 'to',
                      'and', 'or', 'but', 'not', 'with', 'for', 'of', 'when', 'how',
                      'what', 'that', 'this', 'has', 'have', 'been', 'was', 'are',
                      'keep', 'keeps', 'keeping', 'get', 'gets', 'getting'}

    if not symptom_words:
        return None

    # Search using the longest meaningful word
    search_word = max(symptom_words, key=len) if symptom_words else ''
    if len(search_word) < 3:
        return None

    candidates = db.search_facts_keyword(search_word, limit=20)

    best_match = None
    best_score = 0

    for candidate in candidates:
        if candidate.get('superseded_by'):
            continue

        # Calculate word overlap score
        cand_words = set((candidate.get('symptom', '') + ' ' +
                         (candidate.get('diagnosis', '') or '') + ' ' +
                         (candidate.get('resolution', '') or '')).lower().split())
        cand_words -= {'the', 'a', 'an', 'is', 'my', 'it', 'in', 'on', 'to', 'and', 'or'}

        if not cand_words:
            continue

        # Jaccard similarity
        all_words = set()
        if diagnosis:
            all_words |= set(diagnosis.lower().split())
        if resolution:
            all_words |= set(resolution.lower().split())
        query_words = symptom_words | all_words

        intersection = query_words & cand_words
        union = query_words | cand_words
        score = len(intersection) / len(union) if union else 0

        if score > best_score and score > 0.4:  # 40% overlap threshold
            best_score = score
            best_match = candidate

    return best_match


def record_outcome(db, session_id: str, outcome: str, satisfaction: int = None):
    """
    Record a session outcome and update related facts.
    outcome: 'resolved', 'partial', 'unresolved', 'wrong_diagnosis'
    """
    from backend.services.memory import get_memory

    memory = get_memory(db, session_id)
    symptoms = memory.get('issue_summary', '')
    tried_fixes = memory.get('tried_fixes', [])
    hardware_focus = memory.get('hardware_focus', [])

    # Build hardware hash
    hw_hash = '_'.join(sorted(hardware_focus)) if hardware_focus else None

    # Get provider info from session
    provider = None  # TODO: track this in session memory

    # Record session outcome
    db.create_session_outcome(
        session_id=session_id,
        outcome=outcome,
        symptoms=json.dumps(symptoms) if symptoms else None,
        resolution=json.dumps(tried_fixes[-1]) if tried_fixes else None,
        provider=provider,
        hardware_hash=hw_hash,
        satisfaction=satisfaction,
    )

    # If unresolved or wrong, create/update a knowledge gap
    if outcome in ('unresolved', 'wrong_diagnosis') and symptoms:
        gap_type = 'wrong_diagnosis' if outcome == 'wrong_diagnosis' else 'no_resolution'
        db.create_or_update_gap(symptoms, gap_type)
        logger.info(f"Knowledge gap recorded: {symptoms[:50]} ({gap_type})")

    logger.info(f"Session outcome recorded: {session_id} -> {outcome}")


# ============================================================================
# Context Assembly — The core of "learning"
# ============================================================================

def build_brain_context(db, user_description: str, session_id: str = None) -> str:
    """
    Build the brain's context section for AI prompt injection.
    This is WHERE LEARNING MANIFESTS — high-confidence facts first,
    failed approaches deprioritized, knowledge gaps surfaced.
    """
    parts = []

    # 1. Find relevant facts
    relevant_facts = _find_relevant_facts(db, user_description)
    if relevant_facts:
        fact_lines = []
        for fact, score in relevant_facts[:MAX_FACTS_IN_CONTEXT]:
            success = fact.get('success_count', 0)
            failure = fact.get('failure_count', 0)
            total = success + failure
            confidence_pct = int(fact.get('confidence', 0.5) * 100)

            line = f"- Symptom: {fact['symptom']}"
            if fact.get('diagnosis'):
                line += f"\n  Diagnosis: {fact['diagnosis']}"
            if fact.get('resolution'):
                line += f"\n  Resolution: {fact['resolution']}"
            if total > 0:
                line += f"\n  Track record: {success}/{total} successes ({confidence_pct}% confidence)"
            else:
                line += f"\n  Confidence: {confidence_pct}% (no outcome data yet)"

            fact_lines.append(line)

        parts.append(
            "TROUBLESHOOTING KNOWLEDGE (from past experience -- prioritize high-confidence fixes):\n" +
            "\n".join(fact_lines)
        )

    # 2. Knowledge gaps
    gaps = _find_relevant_gaps(db, user_description)
    if gaps:
        gap_lines = []
        for gap in gaps[:MAX_GAPS_IN_CONTEXT]:
            gap_lines.append(
                f"- \"{gap['symptom_description']}\" ({gap['gap_type']}, seen {gap['frequency']}x)"
            )
        parts.append(
            "KNOWLEDGE GAPS (areas of uncertainty -- ask more questions before diagnosing):\n" +
            "\n".join(gap_lines)
        )

    # 3. Outcome stats (how good is the brain overall?)
    try:
        stats = db.get_outcome_stats()
        if stats.get('total', 0) > 0:
            rate = stats.get('resolution_rate', 0)
            parts.append(
                f"BRAIN STATS: {stats['total']} past sessions, "
                f"{int(rate * 100)}% resolution rate"
            )
    except Exception:
        pass

    if not parts:
        return ""

    return "\n\n".join(parts)


def _find_relevant_facts(db, description: str) -> List[tuple]:
    """
    Find facts relevant to the user's description.
    Returns list of (fact_dict, combined_score) tuples, sorted by score.
    """
    if not description or len(description.strip()) < 5:
        return []

    # Keyword search (Phase 2D will add vector search)
    # Split description into key terms and search for each
    words = description.lower().split()
    meaningful = [w for w in words if len(w) > 3 and w not in
                  {'the', 'and', 'but', 'not', 'with', 'for', 'when', 'how',
                   'what', 'that', 'this', 'have', 'been', 'keep', 'keeps',
                   'getting', 'does', 'from', 'just', 'like', 'into', 'also',
                   'some', 'than', 'then', 'them', 'they', 'there', 'these',
                   'about', 'would', 'could', 'should', 'very', 'really'}]

    if not meaningful:
        return []

    all_facts = {}
    for word in meaningful[:5]:  # Search top 5 meaningful words
        results = db.search_facts_keyword(word, limit=10)
        for fact in results:
            fid = fact['id']
            if fid not in all_facts:
                all_facts[fid] = fact

    if not all_facts:
        return []

    # Score each fact: confidence * decay * relevance
    scored = []
    for fact in all_facts.values():
        if fact.get('superseded_by'):
            continue

        confidence = fact.get('confidence', 0.5)
        decay = calculate_decay(fact.get('last_accessed'))

        # Relevance: how many query words match
        fact_text = (fact.get('symptom', '') + ' ' +
                     (fact.get('diagnosis', '') or '') + ' ' +
                     (fact.get('resolution', '') or '')).lower()
        relevance = sum(1 for w in meaningful if w in fact_text) / len(meaningful)

        combined = confidence * decay * relevance

        if combined >= MIN_CONFIDENCE_FOR_CONTEXT:
            scored.append((fact, combined))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def _find_relevant_gaps(db, description: str) -> List[Dict[str, Any]]:
    """Find knowledge gaps relevant to the description."""
    gaps = db.get_open_gaps(limit=10)
    if not gaps or not description:
        return []

    desc_lower = description.lower()
    relevant = []
    for gap in gaps:
        gap_text = gap.get('symptom_description', '').lower()
        # Check if any significant words overlap
        gap_words = set(gap_text.split()) - {'the', 'a', 'my', 'is', 'in'}
        desc_words = set(desc_lower.split()) - {'the', 'a', 'my', 'is', 'in'}
        overlap = gap_words & desc_words
        if len(overlap) >= 2 or any(w in desc_lower for w in gap_words if len(w) > 4):
            relevant.append(gap)

    return relevant


# ============================================================================
# Nightly Maintenance
# ============================================================================

def run_nightly_decay(db):
    """
    Update decay scores and activation tiers for all facts.
    Should be called by a scheduler (e.g., daily at 3 AM).
    """
    facts = db.get_all_facts(limit=1000)
    updated = 0
    for fact in facts:
        decay = calculate_decay(fact.get('last_accessed'))
        tier = get_activation_tier(fact.get('last_accessed'))
        if abs(decay - fact.get('decay_score', 1.0)) > 0.01 or tier != fact.get('activation_tier'):
            db.update_fact_decay(fact['id'], round(decay, 4), tier)
            updated += 1

    logger.info(f"Nightly decay: updated {updated}/{len(facts)} facts")
    return updated
