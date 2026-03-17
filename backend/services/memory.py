"""
Session Memory Service — working memory for troubleshooting sessions.

Manages per-session context so the AI remembers what's been discussed,
what fixes have been tried, and what facts have been discovered.
Inspired by H3's scratch_entries working memory system.

Memory keys:
  - issue_summary: One-line summary of current problem
  - tried_fixes: JSON array [{fix, outcome, timestamp}]
  - key_facts: JSON array of important facts discovered
  - diagnostic_state: gathering_info | diagnosing | trying_fixes | resolved
  - hardware_focus: JSON array of relevant component types
  - abnormal_readings: JSON array of flagged hardware anomalies
"""

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Valid diagnostic states
DIAGNOSTIC_STATES = ['gathering_info', 'diagnosing', 'trying_fixes', 'resolved']


def create_session(db) -> str:
    """Create a new session and return its ID."""
    session_id = str(uuid.uuid4())[:12]
    # Initialize with default state
    db.set_session_memory(session_id, 'diagnostic_state', 'gathering_info')
    db.set_session_memory(session_id, 'tried_fixes', '[]')
    db.set_session_memory(session_id, 'key_facts', '[]')
    db.set_session_memory(session_id, 'hardware_focus', '[]')
    db.set_session_memory(session_id, 'abnormal_readings', '[]')
    logger.info(f"Created session {session_id}")
    return session_id


def get_memory(db, session_id: str) -> Dict[str, Any]:
    """Get all session memory as a structured dict with parsed JSON values."""
    raw = db.get_session_memory(session_id)
    if not raw:
        return {}

    result = {}
    for key, value in raw.items():
        # Parse JSON arrays/objects
        if key in ('tried_fixes', 'key_facts', 'hardware_focus', 'abnormal_readings'):
            try:
                result[key] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                result[key] = []
        else:
            result[key] = value
    return result


def set_memory(db, session_id: str, key: str, value: Any):
    """Set a memory entry. Auto-serializes lists/dicts to JSON."""
    if isinstance(value, (list, dict)):
        value = json.dumps(value)
    db.set_session_memory(session_id, key, str(value))


def add_tried_fix(db, session_id: str, fix_description: str, outcome: str):
    """Add a fix attempt to the tried_fixes list."""
    memory = get_memory(db, session_id)
    tried = memory.get('tried_fixes', [])
    tried.append({
        'fix': fix_description,
        'outcome': outcome,
        'timestamp': datetime.now().isoformat(),
    })
    set_memory(db, session_id, 'tried_fixes', tried)

    # If we're adding fixes, we're in the trying_fixes state
    if memory.get('diagnostic_state') != 'resolved':
        set_memory(db, session_id, 'diagnostic_state', 'trying_fixes')


def add_key_fact(db, session_id: str, fact: str):
    """Add a key fact, avoiding duplicates."""
    memory = get_memory(db, session_id)
    facts = memory.get('key_facts', [])
    # Avoid duplicates (case-insensitive)
    if not any(f.lower().strip() == fact.lower().strip() for f in facts):
        facts.append(fact)
        set_memory(db, session_id, 'key_facts', facts)


def add_hardware_focus(db, session_id: str, component: str):
    """Add a hardware component to the focus list."""
    memory = get_memory(db, session_id)
    focus = memory.get('hardware_focus', [])
    if component.lower() not in [f.lower() for f in focus]:
        focus.append(component.lower())
        set_memory(db, session_id, 'hardware_focus', focus)


def add_abnormal_reading(db, session_id: str, reading: str):
    """Flag an abnormal hardware reading."""
    memory = get_memory(db, session_id)
    abnormal = memory.get('abnormal_readings', [])
    if reading not in abnormal:
        abnormal.append(reading)
        set_memory(db, session_id, 'abnormal_readings', abnormal)


# ============================================================================
# Rule-Based Memory Extraction
# ============================================================================

# Patterns for detecting tried fixes
FIX_TRIED_PATTERNS = [
    # "I tried X" / "I already tried X"
    re.compile(r"i\s+(?:already\s+)?tried\s+(.+?)(?:\.|,|$|but|and)", re.IGNORECASE),
    # "X didn't work" / "X didn't help"
    re.compile(r"(.+?)\s+didn'?t\s+(?:work|help|fix|solve)", re.IGNORECASE),
    # "already did X" / "already done X"
    re.compile(r"already\s+(?:did|done)\s+(.+?)(?:\.|,|$|but|and)", re.IGNORECASE),
    # "X made no difference"
    re.compile(r"(.+?)\s+made\s+no\s+difference", re.IGNORECASE),
]

# Patterns for detecting key facts
FACT_PATTERNS = [
    # "it started when..." / "it started after..."
    re.compile(r"(?:it|this)\s+started\s+(?:when|after|since)\s+(.+?)(?:\.|$)", re.IGNORECASE),
    # "it only happens when..." / "it happens every time..."
    re.compile(r"it\s+(?:only\s+)?happens\s+(?:when|every|during)\s+(.+?)(?:\.|$)", re.IGNORECASE),
    # "it doesn't happen when..." / "it works fine when..."
    re.compile(r"it\s+(?:doesn'?t\s+happen|works?\s+fine)\s+(?:when|during|in)\s+(.+?)(?:\.|$)", re.IGNORECASE),
    # "I noticed that..."
    re.compile(r"i\s+noticed\s+(?:that\s+)?(.+?)(?:\.|$)", re.IGNORECASE),
    # "the problem is..." / "the issue is..."
    re.compile(r"the\s+(?:problem|issue|error)\s+is\s+(.+?)(?:\.|$)", re.IGNORECASE),
]

# Patterns for detecting resolution
RESOLVED_PATTERNS = [
    re.compile(r"(?:that|it)\s+(?:fixed|solved|resolved|worked)", re.IGNORECASE),
    re.compile(r"(?:it'?s|that'?s)\s+(?:working|fixed|solved|better)\s+now", re.IGNORECASE),
    re.compile(r"problem\s+(?:is\s+)?(?:gone|fixed|solved|resolved)", re.IGNORECASE),
]

# Hardware component keywords for focus detection
HARDWARE_KEYWORDS = {
    'gpu': ['gpu', 'graphics', 'nvidia', 'geforce', 'rtx', 'gtx', 'video card', 'display adapter', 'vram'],
    'cpu': ['cpu', 'processor', 'ryzen', 'intel', 'core', 'amd', 'thread'],
    'memory': ['ram', 'memory', 'ddr', 'dimm'],
    'storage': ['ssd', 'hdd', 'disk', 'hard drive', 'storage', 'nvme', 'sata'],
    'display': ['monitor', 'screen', 'display', 'resolution', 'refresh rate', 'hz', 'displayport', 'hdmi'],
    'network': ['network', 'wifi', 'ethernet', 'internet', 'connection', 'dns', 'router'],
    'motherboard': ['motherboard', 'bios', 'uefi', 'usb', 'pcie'],
    'power': ['psu', 'power supply', 'power', 'wattage', 'ups'],
    'cooling': ['fan', 'cooler', 'temperature', 'thermal', 'overheating', 'temp'],
}


def extract_from_user_message(db, session_id: str, message: str):
    """
    Extract structured facts from a user message using rule-based patterns.
    Updates session memory with any discovered information.
    """
    if not message or len(message.strip()) < 3:
        return

    message_lower = message.lower()

    # Check for tried fixes (only use first match to avoid duplicates)
    fix_found = False
    for pattern in FIX_TRIED_PATTERNS:
        if fix_found:
            break
        match = pattern.search(message)
        if match:
            fix_text = match.group(1).strip()
            # Avoid tiny matches and check it's not already recorded
            if len(fix_text) > 5 and len(fix_text) < 150:
                memory = get_memory(db, session_id)
                tried = memory.get('tried_fixes', [])
                # Skip if this fix is already in the list (fuzzy check)
                already_exists = any(
                    fix_text.lower() in t.get('fix', '').lower() or
                    t.get('fix', '').lower() in fix_text.lower()
                    for t in tried
                )
                if not already_exists:
                    add_tried_fix(db, session_id, fix_text, 'failed')
                    fix_found = True
                    logger.debug(f"Session {session_id}: extracted tried fix: {fix_text}")

    # Check for key facts
    for pattern in FACT_PATTERNS:
        match = pattern.search(message)
        if match:
            fact_text = match.group(1).strip()
            if len(fact_text) > 5:
                add_key_fact(db, session_id, fact_text)
                logger.debug(f"Session {session_id}: extracted fact: {fact_text}")

    # Check for resolution
    for pattern in RESOLVED_PATTERNS:
        if pattern.search(message):
            set_memory(db, session_id, 'diagnostic_state', 'resolved')
            logger.debug(f"Session {session_id}: marked as resolved")
            break

    # Detect hardware focus from keywords
    for component, keywords in HARDWARE_KEYWORDS.items():
        if any(kw in message_lower for kw in keywords):
            add_hardware_focus(db, session_id, component)

    # If no issue_summary yet and message looks like a problem description
    memory = get_memory(db, session_id)
    if not memory.get('issue_summary') and len(message) > 15:
        # Use first sentence or first 100 chars as summary
        first_sentence = message.split('.')[0].strip()
        if len(first_sentence) > 10:
            summary = first_sentence[:120]
            set_memory(db, session_id, 'issue_summary', summary)
            set_memory(db, session_id, 'diagnostic_state', 'diagnosing')
            logger.debug(f"Session {session_id}: set issue summary: {summary}")


def extract_from_ai_response(db, session_id: str, response: str, fixes: list = None):
    """
    Extract relevant info from an AI response to update session memory.
    Primarily tracks which fixes were suggested so we know what's been offered.
    """
    if fixes:
        # AI suggested fixes — update state
        memory = get_memory(db, session_id)
        if memory.get('diagnostic_state') == 'diagnosing':
            set_memory(db, session_id, 'diagnostic_state', 'trying_fixes')


# ============================================================================
# Prompt Building
# ============================================================================

def build_memory_prompt(db, session_id: str) -> str:
    """
    Build the memory context section for injection into AI prompts.
    Returns empty string if no meaningful memory exists.
    """
    memory = get_memory(db, session_id)
    if not memory:
        return ""

    parts = []

    # Issue summary
    summary = memory.get('issue_summary')
    if summary:
        parts.append(f"- Issue: {summary}")

    # Diagnostic state
    state = memory.get('diagnostic_state', 'gathering_info')
    parts.append(f"- Diagnostic state: {state}")

    # Tried fixes
    tried = memory.get('tried_fixes', [])
    if tried:
        fix_lines = []
        for i, t in enumerate(tried, 1):
            outcome = t.get('outcome', 'unknown').upper()
            fix_lines.append(f"  [{i}] \"{t.get('fix', '?')}\" -> {outcome}")
        parts.append("- Tried fixes:\n" + "\n".join(fix_lines))

    # Key facts
    facts = memory.get('key_facts', [])
    if facts:
        parts.append("- Key facts: " + " | ".join(facts))

    # Hardware focus
    focus = memory.get('hardware_focus', [])
    if focus:
        parts.append(f"- Hardware focus: {', '.join(focus)}")

    # Abnormal readings
    abnormal = memory.get('abnormal_readings', [])
    if abnormal:
        parts.append("- Abnormal readings: " + " | ".join(abnormal))

    if not parts:
        return ""

    header = "SESSION MEMORY (what you know so far -- use this to avoid repeating yourself):"
    footer = "\nDO NOT suggest fixes already marked as FAILED above. Build on what you know."

    return header + "\n" + "\n".join(parts) + footer


def check_hardware_anomalies(db, session_id: str):
    """
    Check current hardware readings against reasonable baselines.
    Flag anything unusual and store in session memory.
    """
    try:
        # Get latest snapshot
        cursor = db.execute("SELECT id FROM snapshots ORDER BY timestamp DESC LIMIT 1")
        row = cursor.fetchone()
        if not row:
            return
        snapshot_id = row[0]

        # Check GPU
        gpu = db.get_gpu_state(snapshot_id)
        if gpu:
            temp = gpu.get('temperature_c')
            if temp and temp > 85:
                add_abnormal_reading(db, session_id,
                    f"GPU temperature is {temp}°C (high, normal idle: 30-50°C)")

            vram_total = gpu.get('vram_total_mb', 0)
            vram_used = gpu.get('vram_used_mb', 0)
            if vram_total > 0 and vram_used > 0:
                vram_pct = (vram_used / vram_total) * 100
                if vram_pct > 90:
                    add_abnormal_reading(db, session_id,
                        f"VRAM usage is {vram_pct:.0f}% ({vram_used}MB/{vram_total}MB)")

            power = gpu.get('power_draw_w')
            if power and power > 350:
                add_abnormal_reading(db, session_id,
                    f"GPU power draw is {power}W (unusually high)")

        # Check CPU/Memory from hardware_state
        hw_states = db.get_hardware_states(snapshot_id)
        for hw in hw_states:
            comp_type = hw.get('component_type', '')
            try:
                data = json.loads(hw.get('component_data', '{}'))
            except (json.JSONDecodeError, TypeError):
                continue

            if comp_type == 'cpu' and isinstance(data, dict):
                usage = data.get('usage_percent')
                if usage and usage > 80:
                    add_abnormal_reading(db, session_id,
                        f"CPU usage is {usage}% (high — is something running in the background?)")

                temp = data.get('temperature_c')
                if temp and temp > 90:
                    add_abnormal_reading(db, session_id,
                        f"CPU temperature is {temp}°C (very high, check cooling)")

            elif comp_type == 'memory' and isinstance(data, dict):
                pct = data.get('percent_used')
                if pct and pct > 90:
                    add_abnormal_reading(db, session_id,
                        f"RAM usage is {pct}% ({data.get('used_gb', '?')}GB/{data.get('total_gb', '?')}GB)")

            elif comp_type == 'storage' and isinstance(data, dict):
                drives = data.get('drives', [])
                for drive in drives:
                    if isinstance(drive, dict):
                        pct = drive.get('percent_used')
                        letter = drive.get('letter', '?')
                        if pct and pct > 90:
                            add_abnormal_reading(db, session_id,
                                f"Drive {letter} is {pct}% full")

    except Exception as e:
        logger.warning(f"Hardware anomaly check failed: {e}")
