"""
Metabolism Service — Phase 2C of the Living Brain.

After each troubleshooting session ends, the metabolism "digests" the conversation
into structured facts and stores them in the brain. This is how Pulse learns
automatically from every interaction.

Flow:
  Session ends with outcome
  -> Collect: full conversation history, diagnosis, fixes tried, outcome
  -> Send to Ollama (qwen3:30b-a3b, the batch worker — free and fast)
  -> Parse structured facts from LLM response
  -> Store in troubleshooting_facts table (with deduplication)
  -> Create fact_relations (symptom -> diagnosis, diagnosis -> resolution)
  -> Update confidence based on outcome

The batch worker model (qwen3:30b-a3b) is used because:
  - It's fast (~100 tok/s) and free
  - Fact extraction is structured/template work, not deep reasoning
  - Keeps the primary model (qwen3.5:35b) free for user interaction
"""

import json
import logging
import threading
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# The model used for fact extraction (batch worker)
METABOLISM_MODEL = "qwen3:30b-a3b"

# Extraction prompt — instructs the LLM to extract structured facts
EXTRACTION_PROMPT = """You are a knowledge extraction system. Analyze this troubleshooting session and extract structured facts.

Return a JSON object with this exact structure:
{
  "facts": [
    {
      "symptom": "what the user experienced (be specific)",
      "diagnosis": "what was determined to be wrong (or null if unknown)",
      "resolution": "what fixed it or was attempted (or null if nothing tried)",
      "worked": true/false/null,
      "hardware_relevant": ["gpu", "driver", "display", etc.],
      "confidence_note": "brief note on how certain the diagnosis was"
    }
  ],
  "relations": [
    {
      "from_symptom": "symptom text matching a fact above",
      "to_diagnosis": "diagnosis text matching a fact above",
      "relation_type": "causes"
    }
  ]
}

Rules:
- Extract 1-5 facts (prefer fewer, higher-quality facts over many vague ones)
- Be SPECIFIC — "GPU driver crash (nvlddmkm)" not just "driver issue"
- Include hardware context when relevant (GPU model, driver version, OS version)
- Set "worked" to true only if the user confirmed the fix resolved the issue
- Set "worked" to false if the fix was tried but didn't help
- Set "worked" to null if no fix was attempted or outcome is unknown
- relation_type must be one of: causes, resolves, co-occurs, contradicts
- If the session had no useful troubleshooting content (just greetings, off-topic), return {"facts": [], "relations": []}
- Return ONLY valid JSON, no markdown, no explanation"""


def digest_session(db, session_id: str, outcome: str, conversation: List[Dict[str, str]]):
    """
    Digest a completed session into structured facts for the brain.

    Args:
        db: Database instance
        session_id: The session that just ended
        outcome: resolved, partial, unresolved, wrong_diagnosis
        conversation: List of {role, content} message dicts
    """
    if not conversation or len(conversation) < 2:
        logger.info(f"Metabolism: skipping session {session_id} — too short ({len(conversation)} messages)")
        return

    # Build the session summary for the LLM
    session_text = _build_session_text(db, session_id, outcome, conversation)

    # Call the batch worker model for extraction
    try:
        extracted = _extract_facts_from_llm(session_text)
    except Exception as e:
        logger.error(f"Metabolism: LLM extraction failed for session {session_id}: {e}")
        return

    if not extracted or not extracted.get('facts'):
        logger.info(f"Metabolism: no facts extracted from session {session_id}")
        return

    # Store extracted facts in the brain
    facts_stored = 0
    fact_id_map = {}  # Maps symptom text -> fact_id for relation creation

    for fact_data in extracted['facts']:
        try:
            fact_id = _store_fact(db, fact_data, outcome, session_id)
            if fact_id:
                facts_stored += 1
                fact_id_map[fact_data.get('symptom', '')] = fact_id
                if fact_data.get('diagnosis'):
                    fact_id_map[fact_data['diagnosis']] = fact_id
        except Exception as e:
            logger.warning(f"Metabolism: failed to store fact: {e}")

    # Create relations between facts
    relations_created = 0
    for rel_data in extracted.get('relations', []):
        try:
            created = _store_relation(db, rel_data, fact_id_map)
            if created:
                relations_created += 1
        except Exception as e:
            logger.warning(f"Metabolism: failed to store relation: {e}")

    logger.info(
        f"Metabolism: session {session_id} digested — "
        f"{facts_stored} facts stored, {relations_created} relations created"
    )


def digest_session_async(db, session_id: str, outcome: str, conversation: List[Dict[str, str]]):
    """
    Run metabolism in a background thread so it doesn't block the API response.
    Uses the existing db since it was created with check_same_thread=False.
    """
    def _run():
        try:
            digest_session(db, session_id, outcome, conversation)
        except Exception as e:
            logger.error(f"Metabolism async error for session {session_id}: {e}", exc_info=True)

    thread = threading.Thread(target=_run, name=f"metabolism-{session_id}", daemon=True)
    thread.start()
    logger.info(f"Metabolism: started async digestion for session {session_id}")


def _build_session_text(db, session_id: str, outcome: str,
                        conversation: List[Dict[str, str]]) -> str:
    """Build the full session context string for the extraction LLM."""
    from backend.services.memory import get_memory

    parts = []

    # Session outcome
    parts.append(f"SESSION OUTCOME: {outcome}")

    # Session memory (tried fixes, key facts, hardware focus)
    memory = get_memory(db, session_id)
    if memory:
        if memory.get('issue_summary'):
            parts.append(f"ISSUE SUMMARY: {memory['issue_summary']}")
        if memory.get('hardware_focus'):
            parts.append(f"HARDWARE INVOLVED: {', '.join(memory['hardware_focus'])}")
        if memory.get('tried_fixes'):
            fixes_text = []
            for fix in memory['tried_fixes']:
                fixes_text.append(f"  - {fix.get('fix', '?')} -> {fix.get('outcome', '?')}")
            parts.append("FIXES TRIED:\n" + "\n".join(fixes_text))
        if memory.get('abnormal_readings'):
            parts.append("ABNORMAL READINGS: " + " | ".join(memory['abnormal_readings']))

    # Conversation transcript (truncated to keep within token budget)
    parts.append("\nCONVERSATION TRANSCRIPT:")
    token_budget = 3000  # ~3000 words, leaves room for the extraction prompt
    word_count = 0
    for msg in conversation:
        role = msg.get('role', 'unknown').upper()
        content = msg.get('content', '')
        # Truncate very long messages
        if len(content) > 500:
            content = content[:500] + "... [truncated]"
        line = f"{role}: {content}"
        word_count += len(line.split())
        if word_count > token_budget:
            parts.append("... [conversation truncated for length]")
            break
        parts.append(line)

    return "\n\n".join(parts)


def _extract_facts_from_llm(session_text: str) -> Optional[Dict[str, Any]]:
    """Call the batch worker model to extract structured facts."""
    from backend.ai.providers import OllamaProvider, OLLAMA_URL
    import requests

    # Check if batch model is available, fall back to whatever is installed
    available = OllamaProvider.get_available_models()
    model = METABOLISM_MODEL
    if not any(METABOLISM_MODEL.split(":")[0] in m for m in available):
        # Fall back to best available model
        model = OllamaProvider.get_best_model()
        if not model:
            raise RuntimeError("No Ollama models available for metabolism")
        logger.info(f"Metabolism: batch model {METABOLISM_MODEL} not found, using {model}")

    # Use a simplified prompt that asks for JSON directly, and disable thinking
    # mode. Qwen3 MoE models with complex system prompts tend to put everything
    # in the thinking field, returning empty or verbose content instead of JSON.
    # The /no_think token in the user message + simplified prompt helps ensure
    # clean JSON output.
    simple_prompt = (
        "You are a fact extractor. Given a troubleshooting session, return ONLY "
        "a JSON object. No explanation, no markdown, no thinking — just JSON.\n\n"
        "Format: {\"facts\": [{\"symptom\": \"...\", \"diagnosis\": \"...\", "
        "\"resolution\": \"...\", \"worked\": true/false/null, "
        "\"hardware_relevant\": [\"gpu\", ...]}], \"relations\": []}\n\n"
        "Rules: 1-5 facts only. Be specific. Set worked=true only if user confirmed fix."
    )

    user_message = f"/no_think\nExtract facts from this session as JSON:\n\n{session_text}"

    response = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": simple_prompt},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
            "options": {
                "temperature": 0.1,  # Low temp for structured extraction
                "num_predict": 2048,
            },
        },
        timeout=120,
    )

    if response.status_code != 200:
        raise RuntimeError(f"Ollama metabolism error {response.status_code}: {response.text[:300]}")

    result = response.json()
    msg = result.get("message", {})
    content = msg.get("content", "")
    thinking = msg.get("thinking", "")

    # If content is empty but thinking has data, the /no_think didn't work
    # or the model put JSON in the thinking field — try to extract from there
    if not content.strip() and thinking.strip():
        logger.warning(f"Metabolism: model returned empty content but {len(thinking)} chars in thinking field — using thinking")
        content = thinking

    logger.info(f"Metabolism: LLM returned {len(content)} chars content, {len(thinking)} chars thinking")

    # Parse JSON from response (handle markdown code blocks)
    return _parse_json_response(content)


def _parse_json_response(content: str) -> Optional[Dict[str, Any]]:
    """
    Parse JSON from LLM response, handling common formatting issues.
    Qwen3 models often wrap JSON in verbose explanations or thinking blocks,
    so we aggressively search for the JSON object within the text.
    """
    if not content:
        return None

    text = content.strip()

    # Strip any thinking tags (qwen3 thinking mode artifacts)
    if "<think>" in text:
        think_end = text.find("</think>")
        if think_end != -1:
            text = text[think_end + 8:].strip()

    # Strip markdown code blocks if the entire response is a code block
    if text.startswith("```"):
        first_newline = text.index("\n") if "\n" in text else len(text)
        text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    # Try direct parse first
    try:
        result = json.loads(text)
        if isinstance(result, dict) and 'facts' in result:
            return result
    except json.JSONDecodeError:
        pass

    # Find the outermost JSON object containing "facts" — the model often
    # wraps the JSON in chain-of-thought explanation text
    # Strategy: find '{"facts"' and then find its matching closing brace
    facts_start = text.find('{"facts"')
    if facts_start == -1:
        facts_start = text.find('"facts"')
        if facts_start != -1:
            # Find the opening brace before "facts"
            brace_pos = text.rfind('{', 0, facts_start)
            if brace_pos != -1:
                facts_start = brace_pos
            else:
                facts_start = -1

    if facts_start != -1:
        # Find the matching closing brace by counting braces
        depth = 0
        for i in range(facts_start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    candidate = text[facts_start:i + 1]
                    try:
                        result = json.loads(candidate)
                        if isinstance(result, dict) and 'facts' in result:
                            logger.info(f"Metabolism: extracted JSON from position {facts_start}-{i+1} in response")
                            return result
                    except json.JSONDecodeError:
                        pass
                    break

    # Last resort: find ANY JSON object with a "facts" array
    import re
    json_blocks = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text)
    for block in json_blocks:
        try:
            result = json.loads(block)
            if isinstance(result, dict) and 'facts' in result:
                logger.info(f"Metabolism: extracted JSON via regex fallback")
                return result
        except json.JSONDecodeError:
            continue

    logger.warning(f"Metabolism: no JSON with 'facts' found in {len(text)} char response")
    logger.debug(f"Metabolism: response start: {text[:300]}")
    return None


def _store_fact(db, fact_data: Dict[str, Any], session_outcome: str,
                session_id: str) -> Optional[int]:
    """Store a single extracted fact in the brain, with deduplication."""
    from backend.services.brain import record_fact

    symptom = fact_data.get('symptom', '').strip()
    if not symptom or len(symptom) < 5:
        return None

    diagnosis = fact_data.get('diagnosis')
    if diagnosis:
        diagnosis = diagnosis.strip()

    resolution = fact_data.get('resolution')
    if resolution:
        resolution = resolution.strip()

    # Determine if the fix worked based on fact data + session outcome
    worked = fact_data.get('worked')
    if worked is None:
        # Infer from session outcome
        if session_outcome == 'resolved':
            worked = True
        elif session_outcome in ('unresolved', 'wrong_diagnosis'):
            worked = False
        # 'partial' stays as None — ambiguous

    # Build hardware context from the fact's hardware_relevant field
    hw_context = None
    hw_relevant = fact_data.get('hardware_relevant', [])
    if hw_relevant:
        hw_context = {'components': hw_relevant}

    fact_id = record_fact(
        db,
        symptom=symptom,
        diagnosis=diagnosis,
        resolution=resolution,
        worked=worked,
        hardware_context=hw_context,
        source='metabolism',
    )

    return fact_id


def _store_relation(db, rel_data: Dict[str, Any],
                    fact_id_map: Dict[str, int]) -> bool:
    """Store a relation between facts if both exist."""
    from_text = rel_data.get('from_symptom', '')
    to_text = rel_data.get('to_diagnosis', '')
    rel_type = rel_data.get('relation_type', 'co-occurs')

    # Validate relation type
    valid_types = {'causes', 'resolves', 'co_occurs', 'co-occurs', 'contradicts'}
    if rel_type not in valid_types:
        return False

    # Normalize relation type
    rel_type = rel_type.replace('-', '_')

    # Find matching fact IDs
    source_id = fact_id_map.get(from_text)
    target_id = fact_id_map.get(to_text)

    if not source_id or not target_id or source_id == target_id:
        return False

    db.create_fact_relation(source_id, target_id, rel_type)
    return True
