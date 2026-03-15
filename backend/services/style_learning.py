"""
Style Learning Service — learns from user corrections to AI output.

After 3+ corrections in the same scope, generates a style guide using AI.
The guide is injected into future AI prompts so responses match user preferences.
"""

import json
import logging
from typing import Optional

from backend.database import StyleGuide

logger = logging.getLogger(__name__)

# Minimum corrections before generating/regenerating a style guide
MIN_CORRECTIONS_FOR_GUIDE = 3


def maybe_regenerate_guide(db, scope: str) -> Optional[str]:
    """
    Check if a style guide should be (re)generated for the given scope.
    Generates if there are >= 3 new corrections since last generation.

    Args:
        db: Database instance
        scope: 'diagnosis', 'fix_suggestion', or 'chat_response'

    Returns:
        The new guide text, or None if not enough corrections
    """
    existing = db.get_style_guide(scope)
    last_version = existing['version'] if existing else 0
    last_count = existing['correction_count'] if existing else 0

    # Count total corrections for this scope
    # Map scope to correction_type
    type_map = {
        'diagnosis': 'diagnosis_edit',
        'fix_suggestion': 'fix_edit',
        'chat_response': 'response_edit',
    }
    correction_type = type_map.get(scope, scope)
    total_corrections = db.count_corrections(correction_type)

    new_corrections = total_corrections - last_count
    if new_corrections < MIN_CORRECTIONS_FOR_GUIDE:
        return None

    # Get recent corrections for this scope
    corrections = db.get_corrections(correction_type=correction_type, limit=20)
    if len(corrections) < MIN_CORRECTIONS_FOR_GUIDE:
        return None

    # Generate style guide using AI
    guide_text = _generate_guide(db, scope, corrections)
    if not guide_text:
        return None

    # Store new version
    new_guide = StyleGuide(
        scope=scope,
        guide=guide_text,
        sample_count=len(corrections),
        correction_count=total_corrections,
        version=last_version + 1,
    )
    db.create_style_guide(new_guide)

    logger.info(f"Generated style guide v{last_version + 1} for scope '{scope}' from {len(corrections)} corrections")
    return guide_text


def _generate_guide(db, scope: str, corrections: list) -> Optional[str]:
    """Use AI to synthesize a style guide from corrections."""
    # Build the prompt
    examples = []
    for c in corrections[:10]:  # Limit to 10 examples
        examples.append(
            f"ORIGINAL: {c['original_text'][:200]}\n"
            f"CORRECTED TO: {c['corrected_text'][:200]}"
        )

    examples_text = '\n\n'.join(examples)

    prompt = f"""Analyze these corrections a user made to AI-generated {scope} text.
Find patterns in what the user changed and write a concise style guide (3-5 rules)
that would help future responses match the user's preferences.

Focus on: tone, detail level, formatting, terminology preferences, and common corrections.

CORRECTIONS:
{examples_text}

Write ONLY the style guide rules, one per line. No preamble."""

    try:
        from backend.ai.providers import chat_with_failover
        result = chat_with_failover(
            system_prompt="You analyze text corrections and write concise style guides. Output only the rules.",
            user_message=prompt,
            preferred_provider="auto",
        )
        guide = result.get('content', '').strip()
        if guide and len(guide) > 20:
            return guide
    except Exception as e:
        logger.warning(f"AI style guide generation failed: {e}")

    # Fallback: simple rule extraction without AI
    return _simple_guide_extraction(corrections)


def _simple_guide_extraction(corrections: list) -> Optional[str]:
    """
    Basic pattern extraction without AI.
    Looks for common themes in corrections.
    """
    rules = []

    # Check for length changes
    shorter_count = sum(1 for c in corrections if len(c['corrected_text']) < len(c['original_text']) * 0.8)
    longer_count = sum(1 for c in corrections if len(c['corrected_text']) > len(c['original_text']) * 1.2)

    if shorter_count > len(corrections) * 0.5:
        rules.append("Keep responses concise — user prefers shorter explanations.")
    elif longer_count > len(corrections) * 0.5:
        rules.append("Provide more detail — user wants thorough explanations.")

    # Check for technical term changes
    tech_additions = 0
    tech_removals = 0
    for c in corrections:
        orig_words = set(c['original_text'].lower().split())
        corr_words = set(c['corrected_text'].lower().split())
        added = corr_words - orig_words
        removed = orig_words - corr_words
        tech_terms = {'registry', 'command', 'powershell', 'cmd', 'terminal', 'regedit',
                      'service', 'process', 'driver', 'dll', 'exe', 'path'}
        tech_additions += len(added & tech_terms)
        tech_removals += len(removed & tech_terms)

    if tech_additions > tech_removals:
        rules.append("Include specific technical details (commands, paths, registry keys).")
    elif tech_removals > tech_additions:
        rules.append("Use less technical language — explain in plain terms.")

    if rules:
        return '\n'.join(rules)
    return None
