"""
Similarity Matching Service — finds relevant past fixes for new issues.

Scoring formula (H3-inspired):
  score = vector_similarity * 0.7 + decayed_confidence * 0.3
"""

import logging
from typing import List, Dict, Any

from backend.services.embeddings import (
    get_embedding, deserialize_embedding, cosine_similarity,
)
from backend.ai.learning import LearningEngine

logger = logging.getLogger(__name__)


def find_similar_fixes(db, description: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Find past fixes most similar to the given issue description.

    Returns ranked list with: fix title, description, success rate,
    decayed confidence, similarity score, and combined score.
    """
    try:
        query_vec = get_embedding(description)
    except Exception as e:
        logger.warning(f"Could not embed query for similarity search: {e}")
        return []

    # Get all fix embeddings
    fix_embeddings = db.get_embeddings_by_type('fix')
    if not fix_embeddings:
        return []

    learning = LearningEngine(db)
    candidates = []

    for emb_row in fix_embeddings:
        try:
            stored_vec = deserialize_embedding(emb_row['embedding'])
            sim = cosine_similarity(query_vec, stored_vec)

            fix_id = emb_row['entity_id']
            fix = db.get_fix(fix_id)
            if not fix:
                continue

            # Get outcome data for this fix
            outcomes = db.execute(
                "SELECT resolved FROM fix_outcomes WHERE fix_id = ?", (fix_id,)
            ).fetchall()
            total = len(outcomes)
            successes = sum(1 for o in outcomes if o['resolved'])
            success_rate = successes / total if total > 0 else 0.0

            # Get related patterns for confidence
            pattern_confidence = 0.0
            if fix.get('action_type') and fix.get('issue_id'):
                issue = db.get_issue(fix['issue_id'])
                if issue:
                    patterns = learning.get_active_patterns_decayed('fix_effectiveness')
                    for p in patterns:
                        if (fix['action_type'] in p.get('description', '') and
                                issue['issue_type'] in p.get('description', '')):
                            pattern_confidence = p['decayed_confidence']
                            break

            # Combined score: similarity * 0.7 + confidence * 0.3
            combined = sim * 0.7 + pattern_confidence * 0.3

            candidates.append({
                'fix_id': fix_id,
                'title': fix.get('title', ''),
                'description': fix.get('description', ''),
                'action_type': fix.get('action_type', ''),
                'success_rate': round(success_rate, 2),
                'total_attempts': total,
                'similarity': round(sim, 4),
                'pattern_confidence': round(pattern_confidence, 4),
                'combined_score': round(combined, 4),
            })
        except Exception as e:
            logger.debug(f"Error processing fix embedding {emb_row.get('entity_id')}: {e}")
            continue

    # Sort by combined score, return top N
    candidates.sort(key=lambda x: x['combined_score'], reverse=True)
    return candidates[:limit]
