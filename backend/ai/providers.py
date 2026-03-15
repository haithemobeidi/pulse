"""
AI Provider Abstraction

Supports multiple AI backends with automatic failover:
1. Ollama (local) - Free, fast, private. Default.
2. Google Gemini - User's existing subscription. Primary fallback.
3. Claude API - Pay-per-use backup.

Auto-failover: Local → Gemini → Claude
If a GPU issue is detected in the problem description, skips local automatically.
"""

import json
import os
import logging
import base64
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Provider endpoints
# Ollama runs on Windows - WSL reaches it via the gateway IP
# Falls back to localhost for non-WSL environments
def _get_ollama_url():
    import os
    custom = os.environ.get("OLLAMA_HOST_URL")
    if custom:
        return custom
    # Try to detect WSL and use gateway IP
    try:
        with open("/proc/version", "r") as f:
            if "microsoft" in f.read().lower():
                # We're in WSL - read the default gateway
                import subprocess
                result = subprocess.run(
                    ["ip", "route", "show", "default"],
                    capture_output=True, text=True, timeout=3
                )
                if result.returncode == 0:
                    gateway = result.stdout.split()[2]
                    return f"http://{gateway}:11434"
    except Exception:
        pass
    return "http://localhost:11434"

OLLAMA_URL = _get_ollama_url()
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"


def _load_env() -> Dict[str, str]:
    """Load .env file into a dict"""
    env = {}
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                env[key.strip()] = val.strip().strip('"').strip("'")
    return env


def _get_key(name: str) -> Optional[str]:
    """Get a key from env var or .env file"""
    val = os.environ.get(name)
    if val and val not in ("", "your-api-key-here", "your-gemini-api-key-here"):
        return val
    env = _load_env()
    val = env.get(name, "")
    if val and val not in ("your-api-key-here", "your-gemini-api-key-here"):
        return val
    return None


class ProviderStatus:
    """Status of all AI providers"""

    @staticmethod
    def check() -> Dict[str, Any]:
        return {
            "ollama": OllamaProvider.is_available(),
            "gemini": GeminiProvider.is_available(),
            "claude": ClaudeProvider.is_available(),
        }


class OllamaProvider:
    """Local LLM via Ollama"""

    # Models to try in order of preference (best first)
    PREFERRED_MODELS = [
        "qwen2.5:32b",
        "qwen2.5:14b",
        "llama3.3:70b",
        "llama3.1:8b",
        "mistral:7b",
        "gemma2:9b",
    ]

    @staticmethod
    def is_available() -> bool:
        try:
            r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    @staticmethod
    def get_available_models() -> List[str]:
        try:
            r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
            if r.status_code == 200:
                models = r.json().get("models", [])
                return [m["name"] for m in models]
        except Exception:
            pass
        return []

    @staticmethod
    def get_best_model() -> Optional[str]:
        available = OllamaProvider.get_available_models()
        if not available:
            return None

        # Try preferred models first
        for preferred in OllamaProvider.PREFERRED_MODELS:
            for available_model in available:
                if preferred.split(":")[0] in available_model:
                    return available_model

        # Fall back to whatever is installed
        return available[0]

    @staticmethod
    def chat(system_prompt: str, user_message: str, model: str = None, messages: list = None) -> Dict[str, Any]:
        if not model:
            model = OllamaProvider.get_best_model()
            if not model:
                raise RuntimeError("No Ollama models installed")

        # Build messages list — either from conversation history or single message
        if messages:
            chat_messages = [{"role": "system", "content": system_prompt}] + messages
        else:
            chat_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]

        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": chat_messages,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 4096,
                },
            },
            timeout=120,
        )

        if response.status_code != 200:
            raise RuntimeError(f"Ollama error {response.status_code}: {response.text[:300]}")

        result = response.json()
        content = result.get("message", {}).get("content", "")

        return {
            "content": content,
            "model": model,
            "provider": "ollama",
            "tokens_used": {
                "input": result.get("prompt_eval_count", 0),
                "output": result.get("eval_count", 0),
            },
        }


class GeminiProvider:
    """Google Gemini API"""

    @staticmethod
    def is_available() -> bool:
        return _get_key("GEMINI_API_KEY") is not None

    @staticmethod
    def chat(
        system_prompt: str,
        user_message: str,
        image_path: Optional[str] = None,
        messages: list = None,
    ) -> Dict[str, Any]:
        api_key = _get_key("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not configured")

        model = "gemini-2.5-flash"

        # Build contents from conversation history or single message
        if messages:
            contents = []
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        else:
            parts = []
            # Add image if provided (Gemini supports vision)
            if image_path and Path(image_path).exists():
                try:
                    with open(image_path, "rb") as f:
                        img_data = base64.b64encode(f.read()).decode("utf-8")
                    ext = Path(image_path).suffix.lower()
                    mime = {
                        ".png": "image/png",
                        ".jpg": "image/jpeg",
                        ".jpeg": "image/jpeg",
                        ".gif": "image/gif",
                        ".webp": "image/webp",
                    }.get(ext, "image/png")
                    parts.append({"inline_data": {"mime_type": mime, "data": img_data}})
                except Exception as e:
                    logger.warning(f"Could not load image for Gemini: {e}")
            parts.append({"text": user_message})
            contents = [{"parts": parts}]

        # For follow-up messages, don't force JSON response
        gen_config = {
            "temperature": 0.3,
            "maxOutputTokens": 4096,
        }
        if not messages:
            gen_config["responseMimeType"] = "application/json"

        response = requests.post(
            f"{GEMINI_API_URL}/{model}:generateContent",
            params={"key": api_key},
            json={
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "contents": contents,
                "generationConfig": gen_config,
            },
            timeout=60,
        )

        if response.status_code != 200:
            raise RuntimeError(f"Gemini error {response.status_code}: {response.text[:300]}")

        result = response.json()
        content = (
            result.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )

        usage = result.get("usageMetadata", {})

        return {
            "content": content,
            "model": model,
            "provider": "gemini",
            "tokens_used": {
                "input": usage.get("promptTokenCount", 0),
                "output": usage.get("candidatesTokenCount", 0),
            },
        }


class ClaudeProvider:
    """Anthropic Claude API"""

    @staticmethod
    def is_available() -> bool:
        return _get_key("ANTHROPIC_API_KEY") is not None

    @staticmethod
    def chat(
        system_prompt: str,
        user_message: str,
        image_path: Optional[str] = None,
        messages: list = None,
    ) -> Dict[str, Any]:
        api_key = _get_key("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")

        # Build messages from conversation history or single message
        if messages:
            api_messages = []
            for msg in messages:
                api_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        else:
            content_blocks = []
            # Add image if provided (Claude supports vision)
            if image_path and Path(image_path).exists():
                try:
                    with open(image_path, "rb") as f:
                        img_data = base64.b64encode(f.read()).decode("utf-8")
                    ext = Path(image_path).suffix.lower()
                    media_type = {
                        ".png": "image/png",
                        ".jpg": "image/jpeg",
                        ".jpeg": "image/jpeg",
                        ".gif": "image/gif",
                        ".webp": "image/webp",
                    }.get(ext, "image/png")
                    content_blocks.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": img_data},
                    })
                except Exception as e:
                    logger.warning(f"Could not load image for Claude: {e}")
            content_blocks.append({"type": "text", "text": user_message})
            api_messages = [{"role": "user", "content": content_blocks}]

        response = requests.post(
            ANTHROPIC_API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 4096,
                "system": system_prompt,
                "messages": api_messages,
            },
            timeout=60,
        )

        if response.status_code != 200:
            raise RuntimeError(f"Claude error {response.status_code}: {response.text[:300]}")

        result = response.json()
        content = result.get("content", [{}])[0].get("text", "")
        usage = result.get("usage", {})

        return {
            "content": content,
            "model": "claude-sonnet-4-20250514",
            "provider": "claude",
            "tokens_used": {
                "input": usage.get("input_tokens", 0),
                "output": usage.get("output_tokens", 0),
            },
        }


# GPU-related keywords that indicate local model shouldn't be used
GPU_ISSUE_KEYWORDS = [
    "gpu", "graphics", "display", "screen", "monitor", "black screen",
    "artifact", "flickering", "tearing", "nvidia", "amd radeon", "driver crash",
    "nvlddmkm", "display driver", "video card", "rendering", "bsod",
    "blue screen", "black", "blank screen", "no display",
]


def should_skip_local(issue_description: str) -> bool:
    """Check if the issue might be GPU-related, meaning local model could fail"""
    desc_lower = issue_description.lower()
    return any(kw in desc_lower for kw in GPU_ISSUE_KEYWORDS)


def chat_with_failover(
    system_prompt: str,
    user_message: str,
    preferred_provider: str = "auto",
    image_path: Optional[str] = None,
    issue_description: str = "",
    messages: list = None,
) -> Dict[str, Any]:
    """
    Send a chat request with automatic failover between providers.

    Provider priority:
    - "auto": Ollama → Gemini → Claude (skips Ollama if GPU issue detected)
    - "ollama": Ollama only
    - "gemini": Gemini only
    - "claude": Claude only

    Args:
        system_prompt: System prompt for the model
        user_message: User message with context
        preferred_provider: Which provider to use ("auto", "ollama", "gemini", "claude")
        image_path: Optional screenshot path (only Gemini and Claude support vision)
        issue_description: Raw issue description for GPU detection

    Returns:
        Dict with content, model, provider, tokens_used
    """
    errors = []

    if preferred_provider != "auto":
        # Use specific provider
        try:
            if preferred_provider == "ollama":
                return OllamaProvider.chat(system_prompt, user_message, messages=messages)
            elif preferred_provider == "gemini":
                return GeminiProvider.chat(system_prompt, user_message, image_path, messages=messages)
            elif preferred_provider == "claude":
                return ClaudeProvider.chat(system_prompt, user_message, image_path, messages=messages)
            else:
                raise RuntimeError(f"Unknown provider: {preferred_provider}")
        except Exception as e:
            raise RuntimeError(f"{preferred_provider} failed: {e}")

    # Auto mode: try providers in order with smart failover
    skip_local = should_skip_local(issue_description)

    # 1. Try Ollama (unless GPU issue)
    if not skip_local and not image_path:
        try:
            if OllamaProvider.is_available():
                logger.info("Using Ollama (local) for analysis...")
                return OllamaProvider.chat(system_prompt, user_message, messages=messages)
            else:
                errors.append("Ollama not running")
        except Exception as e:
            errors.append(f"Ollama: {e}")
            logger.warning(f"Ollama failed, trying Gemini: {e}")
    elif skip_local:
        errors.append(f"Skipped Ollama (GPU-related issue detected)")
        logger.info("GPU issue detected, skipping local model")

    # 2. Try Gemini
    try:
        if GeminiProvider.is_available():
            logger.info("Using Gemini for analysis...")
            return GeminiProvider.chat(system_prompt, user_message, image_path, messages=messages)
        else:
            errors.append("Gemini API key not configured")
    except Exception as e:
        errors.append(f"Gemini: {e}")
        logger.warning(f"Gemini failed, trying Claude: {e}")

    # 3. Try Claude
    try:
        if ClaudeProvider.is_available():
            logger.info("Using Claude for analysis...")
            return ClaudeProvider.chat(system_prompt, user_message, image_path, messages=messages)
        else:
            errors.append("Claude API key not configured")
    except Exception as e:
        errors.append(f"Claude: {e}")

    # All providers failed
    raise RuntimeError(
        f"All AI providers failed:\n" + "\n".join(f"  - {e}" for e in errors)
    )
