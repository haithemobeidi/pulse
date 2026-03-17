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


SYSTEM_PROMPT = """You are Pulse, a Windows PC troubleshooting assistant. You help users diagnose and fix PC problems through conversation.

CRITICAL RULES:
1. FOCUS ON WHAT THE USER SAID. Their description is the primary input. System data is supporting evidence — do NOT diagnose problems they didn't mention.
2. If the user says "check the timeline" or "look at recent events", THEN focus on timeline data. Otherwise, use it only if it's clearly relevant to their stated problem.
3. If a screenshot description is provided, analyze what the screenshot shows and relate it to the user's problem.
4. Ask clarifying questions when the problem is vague. Don't jump to conclusions.
5. Never suggest deleting files, formatting drives, or reinstalling Windows unless truly warranted.
6. Always prefer the least invasive fix first.
7. For each fix, specify EXACT steps: commands, registry paths, settings.
8. If the system data doesn't relate to the user's problem, say so — don't force a connection.
9. NEVER suggest running commands that delete data without explicit warning.
10. Keep the diagnosis conversational and clear, not overly technical.

RESPONSE FORMAT:
Respond ONLY with valid JSON (no markdown, no text outside the JSON):
{
  "diagnosis": "Clear description focused on the user's stated problem",
  "confidence": 0.0-1.0,
  "root_cause": "Most likely root cause based on what the user described + supporting evidence",
  "suggested_fixes": [
    {
      "title": "Short title",
      "description": "What this does and why it helps",
      "risk_level": "none|low|medium|high|critical",
      "action_type": "command|registry|service|manual|setting|download",
      "action_detail": "Exact command or steps",
      "estimated_success": 0.0-1.0,
      "reversible": true|false
    }
  ],
  "questions": ["Questions to better understand the problem — always ask at least one"],
  "preventive_tips": "Prevention advice if applicable",
  "related_patterns": "Relevant patterns from system data, if any"
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
        "similar_past_fixes": [],
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

        # Get learned patterns with decayed confidence
        try:
            from backend.ai.learning import LearningEngine
            learning = LearningEngine(db)
            patterns = learning.get_active_patterns_decayed()
            if patterns:
                context["learned_patterns"] = [
                    {"type": p["pattern_type"], "description": p["description"],
                     "confidence": p["confidence"], "decayed_confidence": p["decayed_confidence"],
                     "times_seen": p["times_seen"], "times_failed": p.get("times_failed", 0)}
                    for p in patterns[:10]  # Top 10 by decayed confidence
                ]
        except Exception as e:
            logger.warning(f"Could not get patterns: {e}")

        # Get similar past fixes via embeddings
        try:
            from backend.services.matching import find_similar_fixes
            similar = find_similar_fixes(db, issue_description, limit=3)
            if similar:
                context["similar_past_fixes"] = similar
        except Exception as e:
            logger.warning(f"Could not get similar fixes: {e}")

        # Get active style guide
        try:
            guide = db.get_style_guide('diagnosis')
            if guide:
                context["style_guide"] = guide['guide']
        except Exception as e:
            logger.warning(f"Could not get style guide: {e}")

    except Exception as e:
        logger.error(f"Error building context: {e}")

    return context


def _describe_image(image_path: str) -> Optional[str]:
    """
    Use a vision-capable model (Gemini or Claude) to describe a screenshot.
    Returns a text description that can be fed to a text-only model like Ollama.
    """
    describe_prompt = """Describe this screenshot in detail for a PC troubleshooting context.
Focus on: error messages, dialog boxes, blue screens, application windows, system notifications,
performance graphs, or anything that indicates a problem. Be specific about any text visible.
Keep it concise but thorough — 2-4 sentences."""

    # Try Gemini first (free tier)
    try:
        if GeminiProvider.is_available():
            logger.info("Using Gemini to describe screenshot...")
            result = GeminiProvider.chat(
                system_prompt="You describe screenshots for PC troubleshooting. Be concise and specific.",
                user_message=describe_prompt,
                image_path=image_path,
            )
            description = result.get("content", "").strip()
            if description:
                return description
    except Exception as e:
        logger.warning(f"Gemini image description failed: {e}")

    # Try Claude as fallback
    try:
        if ClaudeProvider.is_available():
            logger.info("Using Claude to describe screenshot...")
            result = ClaudeProvider.chat(
                system_prompt="You describe screenshots for PC troubleshooting. Be concise and specific.",
                user_message=describe_prompt,
                image_path=image_path,
            )
            description = result.get("content", "").strip()
            if description:
                return description
    except Exception as e:
        logger.warning(f"Claude image description failed: {e}")

    logger.warning("No vision-capable provider available to describe screenshot")
    return None


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

    # Build a clean, structured user message
    hw = context.get('hardware', {})
    gpu = hw.get('gpu', {})
    cpu_data = hw.get('cpu', {}).get('component_data', {})
    mem_data = hw.get('memory', {}).get('component_data', {})
    mb_data = hw.get('motherboard', {}).get('component_data', {})

    # Hardware summary (compact, not raw JSON dump)
    hw_summary = []
    if gpu:
        hw_summary.append(f"GPU: {gpu.get('gpu_name', 'Unknown')} (Driver: {gpu.get('driver_version', '?')}, VRAM: {gpu.get('vram_total_mb', 0) // 1024}GB, Temp: {gpu.get('temperature_c', '?')}°C)")
    if isinstance(cpu_data, dict) and cpu_data.get('name'):
        hw_summary.append(f"CPU: {cpu_data['name']} ({cpu_data.get('physical_cores', '?')} cores, {cpu_data.get('usage_percent', '?')}% usage)")
    elif isinstance(cpu_data, str):
        try:
            cd = json.loads(cpu_data)
            if cd.get('name'):
                hw_summary.append(f"CPU: {cd['name']} ({cd.get('physical_cores', '?')} cores)")
        except Exception:
            pass
    if isinstance(mem_data, dict) and mem_data.get('total_gb'):
        hw_summary.append(f"RAM: {mem_data['total_gb']}GB {mem_data.get('memory_type', '')} ({mem_data.get('percent_used', '?')}% used)")
    elif isinstance(mem_data, str):
        try:
            md = json.loads(mem_data)
            if md.get('total_gb'):
                hw_summary.append(f"RAM: {md['total_gb']}GB {md.get('memory_type', '')} ({md.get('percent_used', '?')}% used)")
        except Exception:
            pass
    if isinstance(mb_data, dict) and mb_data.get('product'):
        hw_summary.append(f"Motherboard: {mb_data.get('manufacturer', '')} {mb_data['product']}")
    elif isinstance(mb_data, str):
        try:
            mbd = json.loads(mb_data)
            if mbd.get('product'):
                hw_summary.append(f"Motherboard: {mbd.get('manufacturer', '')} {mbd['product']}")
        except Exception:
            pass

    monitors = hw.get('monitors', [])
    if monitors:
        mon_list = ', '.join(f"{m.get('monitor_name', '?')} ({m.get('connection_type', '?')})" for m in monitors)
        hw_summary.append(f"Monitors: {mon_list}")

    # Reliability summary (compact — only relevant events, not full dump)
    rel = context.get('reliability', {})
    rel_summary = ""
    if rel.get('records'):
        crashes = [r for r in rel['records'] if 'crash' in r.get('record_type', '')]
        installs = [r for r in rel['records'] if 'install' in r.get('record_type', '')]
        updates = [r for r in rel['records'] if 'update' in r.get('record_type', '')]
        parts = []
        if crashes:
            parts.append(f"{len(crashes)} crash(es): " + '; '.join(
                f"{r.get('source_name', '?')} ({r.get('event_time', '?')})" for r in crashes[:5]
            ))
        if installs:
            parts.append(f"{len(installs)} install(s): " + '; '.join(
                f"{r.get('product_name', r.get('source_name', '?'))} ({r.get('event_time', '?')})" for r in installs[:5]
            ))
        if updates:
            parts.append(f"{len(updates)} update(s)")
        if rel.get('stability_index'):
            parts.append(f"Stability index: {rel['stability_index']}/10")
        rel_summary = '\n'.join(parts)

    # Recent issues summary
    issues_summary = ""
    recent = context.get('recent_issues', [])
    if recent:
        issues_summary = '\n'.join(
            f"- [{i.get('timestamp', '?')}] {i.get('issue_type', '?')}: {i.get('description', '')[:100]}"
            for i in recent[:5]
        )

    # Similar past fixes section
    similar_fixes_summary = ""
    similar = context.get('similar_past_fixes', [])
    if similar:
        similar_fixes_summary = '\n'.join(
            f"- {f['title']} (success rate: {int(f['success_rate']*100)}%, "
            f"similarity: {int(f['similarity']*100)}%, "
            f"confidence: {int(f['pattern_confidence']*100)}%): {f['description'][:150]}"
            for f in similar[:3]
        )

    # Learned patterns section
    patterns_summary = ""
    learned = context.get('learned_patterns', [])
    if learned:
        patterns_summary = '\n'.join(
            f"- [{p['type']}] {p['description']} "
            f"(confidence: {int(p.get('decayed_confidence', p['confidence'])*100)}%, "
            f"seen {p['times_seen']}x)"
            for p in learned[:5]
        )

    # Style guide injection
    style_instruction = ""
    if context.get('style_guide'):
        style_instruction = f"\n\nSTYLE GUIDELINES (follow these when writing your response):\n{context['style_guide']}"

    # Web search for current information about the problem
    web_search_section = ""
    try:
        from backend.services.web_search import search_for_issue
        web_context = search_for_issue(db, issue_description)
        if web_context:
            web_search_section = f"\n\n{web_context}"
            logger.info(f"Web search context injected ({len(web_context)} chars)")
    except Exception as e:
        logger.warning(f"Web search failed (non-critical): {e}")

    user_message = f"""USER'S PROBLEM (this is what you should focus on):
{issue_description}

SYSTEM HARDWARE:
{chr(10).join(hw_summary) if hw_summary else 'No hardware data available'}

RECENT SYSTEM EVENTS (use as supporting evidence only -- do NOT diagnose these unless the user asked about them):
{rel_summary if rel_summary else 'No recent events'}

RECENT ISSUES REPORTED BY USER:
{issues_summary if issues_summary else 'No recent issues'}

SIMILAR PAST FIXES (fixes that worked for similar problems -- reference these if relevant):
{similar_fixes_summary if similar_fixes_summary else 'No similar past fixes yet'}

LEARNED PATTERNS (confidence-weighted insights from past diagnoses):
{patterns_summary if patterns_summary else 'No patterns learned yet'}{web_search_section}{style_instruction}

Remember: Focus on what the user described. The system data is context, not the problem. If web search results contain specific information about the user's hardware or driver version, USE that information to give targeted advice rather than generic suggestions. Respond ONLY with valid JSON."""

    try:
        # If screenshot provided and using a non-vision model (Ollama),
        # first get a description from a vision-capable model (Gemini/Claude)
        if screenshot_path and preferred_provider in ("ollama", "auto"):
            image_description = _describe_image(screenshot_path)
            if image_description:
                user_message = f"SCREENSHOT DESCRIPTION (from image analysis):\n{image_description}\n\n{user_message}"
                logger.info(f"Image described by vision model: {image_description[:100]}...")
                # Don't pass image to Ollama (it can't read it)
                screenshot_path = None

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
