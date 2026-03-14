"""
AI Reasoning Engine

Uses multi-provider AI (Ollama/Gemini/Claude with auto-failover) to analyze
system diagnostic data and provide intelligent troubleshooting suggestions.
Builds context from hardware profile, scan results, reliability data, and
issue history to give personalized diagnoses.
"""

import json
import os
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from backend.ai.providers import (
    chat_with_failover,
    ProviderStatus,
    OllamaProvider,
    GeminiProvider,
    ClaudeProvider,
)

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are Pulse, a Windows PC troubleshooting assistant. You analyze system diagnostic data and help users fix problems.

You have access to the user's actual hardware configuration, reliability monitor data, event logs, and system state. Use this data to provide specific, actionable diagnoses.

RULES:
1. Never suggest deleting files, formatting drives, or reinstalling Windows unless the situation truly warrants it and the user explicitly asks.
2. Always prefer the least invasive fix first.
3. For each fix, specify the EXACT action: the precise command, registry path, setting, or steps.
4. Rate your confidence in the diagnosis from 0.0 to 1.0.
5. Rate each fix's estimated success probability.
6. Classify risk: none, low, medium, high, critical.
7. Reference the user's specific hardware when relevant.
8. If you see patterns from past issues, mention them.
9. Consider recent system changes (driver updates, software installs) as potential causes.
10. NEVER suggest running commands that delete data without explicit warning.

RESPONSE FORMAT:
Respond ONLY with valid JSON matching this schema (no markdown, no explanation outside the JSON):
{
  "diagnosis": "Clear description of what's likely wrong",
  "confidence": 0.0-1.0,
  "root_cause": "Most likely root cause based on the evidence",
  "suggested_fixes": [
    {
      "title": "Short title for this fix",
      "description": "What this fix does and why it should help",
      "risk_level": "none|low|medium|high|critical",
      "action_type": "command|registry|service|manual|setting|download",
      "action_detail": "Exact command, steps, or registry path",
      "estimated_success": 0.0-1.0,
      "reversible": true|false
    }
  ],
  "questions": ["Clarifying questions if you need more info"],
  "preventive_tips": "What the user can do to prevent this in the future",
  "related_patterns": "Any patterns you notice from the data"
}"""


def has_any_provider() -> bool:
    """Check if any AI provider is available"""
    status = ProviderStatus.check()
    return any(status.values())


def get_provider_status() -> Dict[str, Any]:
    """Get detailed status of all providers"""
    status = ProviderStatus.check()
    result = {
        "any_available": any(status.values()),
        "providers": {}
    }

    result["providers"]["ollama"] = {
        "available": status["ollama"],
        "description": "Local AI (free, private, fast)",
        "models": OllamaProvider.get_available_models() if status["ollama"] else [],
        "note": "Install Ollama and pull a model to enable",
    }

    result["providers"]["gemini"] = {
        "available": status["gemini"],
        "description": "Google Gemini (your subscription)",
        "note": "Set GEMINI_API_KEY in .env" if not status["gemini"] else "Ready",
    }

    result["providers"]["claude"] = {
        "available": status["claude"],
        "description": "Anthropic Claude (pay-per-use)",
        "note": "Set ANTHROPIC_API_KEY in .env" if not status["claude"] else "Ready",
    }

    return result


def build_context(db, issue_description: str) -> Dict[str, Any]:
    """
    Build comprehensive context from system data for AI analysis.

    Args:
        db: Database instance
        issue_description: User's description of the problem

    Returns:
        Dict with all context data for the AI prompt
    """
    context = {
        "issue": issue_description,
        "hardware": {},
        "reliability": {},
        "recent_issues": [],
        "learned_patterns": [],
    }

    try:
        # Get latest hardware snapshot
        cursor = db.execute("SELECT id FROM snapshots ORDER BY timestamp DESC LIMIT 1")
        row = cursor.fetchone()

        if row:
            snapshot_id = row[0]

            # GPU info
            gpu = db.get_gpu_state(snapshot_id)
            if gpu:
                context["hardware"]["gpu"] = dict(gpu)

            # Monitor info
            monitors = db.get_monitor_states(snapshot_id)
            if monitors:
                context["hardware"]["monitors"] = [dict(m) for m in monitors]

            # CPU/Memory
            hardware_states = db.get_hardware_states(snapshot_id)
            for hw in hardware_states:
                hw_dict = dict(hw)
                comp_type = hw_dict.get("component_type", "")
                try:
                    hw_dict["component_data"] = json.loads(hw_dict.get("component_data", "{}"))
                except (json.JSONDecodeError, TypeError):
                    pass
                context["hardware"][comp_type] = hw_dict

        # Get recent reliability records
        try:
            reliability = db.get_recent_reliability_records(days=14, limit=30)
            if reliability:
                context["reliability"] = {
                    "records": reliability,
                    "crash_count": sum(1 for r in reliability if "crash" in r.get("record_type", "")),
                    "stability_index": next(
                        (r.get("stability_index") for r in reliability if r.get("stability_index")),
                        None
                    )
                }
        except Exception as e:
            logger.warning(f"Could not get reliability data: {e}")

        # Get recent issues for pattern detection
        try:
            recent_issues = db.get_issues(limit=10)
            context["recent_issues"] = [dict(i) for i in recent_issues]
        except Exception as e:
            logger.warning(f"Could not get recent issues: {e}")

        # Get learned patterns
        try:
            patterns = db.get_active_patterns()
            if patterns:
                context["learned_patterns"] = [
                    {"type": p["pattern_type"], "description": p["description"],
                     "confidence": p["confidence"], "times_seen": p["times_seen"]}
                    for p in patterns if p["confidence"] > 0.3
                ]
        except Exception as e:
            logger.warning(f"Could not get patterns: {e}")

    except Exception as e:
        logger.error(f"Error building context: {e}")

    return context


def analyze_issue(
    db,
    issue_description: str,
    screenshot_path: Optional[str] = None,
    preferred_provider: str = "auto",
) -> Dict[str, Any]:
    """
    Analyze a system issue using AI with multi-provider failover.

    Args:
        db: Database instance
        issue_description: User's description of the problem
        screenshot_path: Optional path to a screenshot for vision analysis
        preferred_provider: "auto", "ollama", "gemini", or "claude"

    Returns:
        AI analysis dict with diagnosis, fixes, confidence, etc.
    """
    if not has_any_provider():
        return {
            "error": "No AI providers configured. Set up Ollama, GEMINI_API_KEY, or ANTHROPIC_API_KEY.",
            "diagnosis": "Cannot analyze without an AI provider",
            "confidence": 0,
            "suggested_fixes": [],
            "provider_status": get_provider_status(),
        }

    # Build context from system data
    context = build_context(db, issue_description)

    # Build the user message with all context
    user_message = f"""I'm having a problem with my PC:

**Problem:** {issue_description}

**My Hardware:**
{json.dumps(context.get('hardware', {}), indent=2, default=str)}

**Reliability Monitor (last 14 days):**
{json.dumps(context.get('reliability', {}), indent=2, default=str)}

**Recent Issues I've Reported:**
{json.dumps(context.get('recent_issues', []), indent=2, default=str)}

**Learned Patterns from Past Fixes:**
{json.dumps(context.get('learned_patterns', []), indent=2, default=str)}

Analyze this problem given my specific hardware and system history. Respond ONLY with valid JSON in the format specified."""

    try:
        # Call AI with failover
        result = chat_with_failover(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            preferred_provider=preferred_provider,
            image_path=screenshot_path,
            issue_description=issue_description,
        )

        content = result.get("content", "")

        # Parse the JSON response
        try:
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                analysis = json.loads(content[json_start:json_end])
            else:
                analysis = {"diagnosis": content, "confidence": 0.5, "suggested_fixes": []}
        except json.JSONDecodeError:
            analysis = {"diagnosis": content, "confidence": 0.5, "suggested_fixes": []}

        # Add provider info
        analysis["provider"] = result.get("provider", "unknown")
        analysis["model"] = result.get("model", "unknown")
        analysis["tokens_used"] = result.get("tokens_used", {})

        logger.info(
            f"AI analysis complete via {result.get('provider')}: "
            f"confidence={analysis.get('confidence', 'N/A')}, "
            f"fixes={len(analysis.get('suggested_fixes', []))}"
        )

        return analysis

    except RuntimeError as e:
        logger.error(f"All AI providers failed: {e}")
        return {
            "error": str(e),
            "diagnosis": f"Analysis failed: {e}",
            "confidence": 0,
            "suggested_fixes": [],
            "provider_status": get_provider_status(),
        }
    except Exception as e:
        logger.error(f"AI analysis failed: {e}")
        return {
            "error": str(e),
            "diagnosis": f"Analysis failed: {e}",
            "confidence": 0,
            "suggested_fixes": [],
        }
