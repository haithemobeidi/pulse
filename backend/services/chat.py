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
7. If session memory shows abnormal hardware readings, proactively mention them and ask clarifying questions (e.g., "I notice your GPU usage is at 80% — are you running a game right now?").
8. NEVER suggest a fix that session memory shows has already been tried and failed.

Respond in plain text (not JSON). Use markdown formatting for readability."""


def _build_system_context(db, last_message_content, session_id=None):
    """Build system hardware context string for chat, using adaptive context + session memory."""
    context_parts = []

    # Session memory (highest priority — goes first)
    if session_id:
        try:
            from backend.services.memory import build_memory_prompt
            memory_prompt = build_memory_prompt(db, session_id)
            if memory_prompt:
                context_parts.append(memory_prompt)
        except Exception as e:
            logger.warning(f"Could not build memory context: {e}")

    # Hardware context
    try:
        from backend.services.context import build_adaptive_context
        context = build_adaptive_context(db, last_message_content, budget_tokens=800)
        hw = context.get('hardware', {})
        gpu = hw.get('gpu', {})
        cpu_data = hw.get('cpu', {}).get('component_data', {})
        mem_data = hw.get('memory', {}).get('component_data', {})

        hw_parts = []
        if gpu:
            hw_parts.append(f"GPU: {gpu.get('gpu_name', '?')} (Driver: {gpu.get('driver_version', '?')})")

        if isinstance(cpu_data, str):
            try:
                cpu_data = json.loads(cpu_data)
            except Exception:
                cpu_data = {}
        if isinstance(cpu_data, dict) and cpu_data.get('name'):
            hw_parts.append(f"CPU: {cpu_data['name']}")

        if isinstance(mem_data, str):
            try:
                mem_data = json.loads(mem_data)
            except Exception:
                mem_data = {}
        if isinstance(mem_data, dict) and mem_data.get('total_gb'):
            hw_parts.append(f"RAM: {mem_data['total_gb']}GB {mem_data.get('memory_type', '')}")

        if hw_parts:
            context_parts.append("User's system: " + " | ".join(hw_parts))

        # Style guide
        style_guide = context.get('style_guide')
        if style_guide:
            context_parts.append(f"Style guidelines: {style_guide}")

    except Exception as e:
        logger.warning(f"Could not build chat context: {e}")

    if context_parts:
        return "\n\n" + "\n\n".join(context_parts)
    return ""


def handle_chat(db, messages, provider='ollama', screenshot_data=None, session_id=None):
    """
    Handle a follow-up chat message.
    Returns dict with response, provider, model.
    """
    if not messages:
        raise ValueError('No messages provided')

    # Build system prompt with hardware context + session memory
    system_context = _build_system_context(db, messages[-1].get('content', ''), session_id=session_id)
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
