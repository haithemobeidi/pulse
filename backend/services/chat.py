"""
Chat Service - conversational follow-up with AI providers.
"""

import json
import logging

from backend.ai.providers import chat_with_failover
from backend.services.screenshots import save_screenshot, describe_screenshot

logger = logging.getLogger(__name__)

CHAT_SYSTEM_PROMPT = """You are Pulse, a Windows PC troubleshooting assistant having a conversation with a user about their PC problems.

You have context from a previous diagnosis. The user is now asking follow-up questions or providing more details. Respond naturally and helpfully.

RULES:
1. Focus on what the user is asking in their latest message.
2. Reference the conversation history to stay consistent.
3. If they provide new information, refine your diagnosis.
4. Be conversational — not overly formal or technical.
5. If suggesting commands or steps, be specific and exact.
6. Keep responses concise but thorough.

Respond in plain text (not JSON). Use markdown formatting for readability."""


def _build_system_context(db, last_message_content):
    """Build system hardware context string for chat, using adaptive context."""
    try:
        # Try adaptive context first
        from backend.services.context import build_adaptive_context
        context = build_adaptive_context(db, last_message_content, budget_tokens=800)
        hw = context.get('hardware', {})
        gpu = hw.get('gpu', {})
        cpu_data = hw.get('cpu', {}).get('component_data', {})
        mem_data = hw.get('memory', {}).get('component_data', {})

        parts = []
        if gpu:
            parts.append(f"GPU: {gpu.get('gpu_name', '?')} (Driver: {gpu.get('driver_version', '?')})")

        if isinstance(cpu_data, str):
            try:
                cpu_data = json.loads(cpu_data)
            except Exception:
                cpu_data = {}
        if isinstance(cpu_data, dict) and cpu_data.get('name'):
            parts.append(f"CPU: {cpu_data['name']}")

        if isinstance(mem_data, str):
            try:
                mem_data = json.loads(mem_data)
            except Exception:
                mem_data = {}
        if isinstance(mem_data, dict) and mem_data.get('total_gb'):
            parts.append(f"RAM: {mem_data['total_gb']}GB {mem_data.get('memory_type', '')}")

        # Add style guide to chat context
        style_guide = context.get('style_guide')
        style_suffix = ""
        if style_guide:
            style_suffix = f"\n\nStyle guidelines: {style_guide}"

        if parts:
            return "\n\nUser's system: " + " | ".join(parts) + style_suffix
        return style_suffix
    except Exception as e:
        logger.warning(f"Could not build chat context: {e}")
    return ""


def handle_chat(db, messages, provider='ollama', screenshot_data=None):
    """
    Handle a follow-up chat message.
    Returns dict with response, provider, model.
    """
    if not messages:
        raise ValueError('No messages provided')

    # Build system prompt with hardware context
    system_context = _build_system_context(db, messages[-1].get('content', ''))
    prompt = CHAT_SYSTEM_PROMPT + system_context

    # Handle screenshot
    chat_messages = list(messages)
    if screenshot_data:
        filepath = save_screenshot(screenshot_data)
        if filepath:
            image_description = describe_screenshot(filepath)
            if image_description and chat_messages:
                last_msg = chat_messages[-1]
                chat_messages[-1] = {
                    'role': last_msg['role'],
                    'content': f"{last_msg['content']}\n\n[Screenshot description: {image_description}]"
                }

    result = chat_with_failover(
        system_prompt=prompt,
        user_message=chat_messages[-1].get('content', ''),
        preferred_provider=provider,
        messages=chat_messages,
    )

    return {
        'response': result.get('content', ''),
        'provider': result.get('provider', 'unknown'),
        'model': result.get('model', 'unknown'),
    }
