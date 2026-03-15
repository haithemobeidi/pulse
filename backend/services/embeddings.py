"""
Embeddings Service — vector embeddings for similarity search.

Uses available AI providers in priority order:
1. Ollama with nomic-embed-text or any embedding model
2. Gemini embedding API
3. Fallback: TF-IDF with scikit-learn (no external API needed)
"""

import json
import logging
import struct
from typing import List, Optional

logger = logging.getLogger(__name__)


def _embed_ollama(text: str) -> Optional[List[float]]:
    """Try to get embeddings from Ollama."""
    try:
        import requests
        from backend.ai.providers import OLLAMA_URL, OllamaProvider

        if not OllamaProvider.is_available():
            return None

        # Try nomic-embed-text first, then any available model
        models = OllamaProvider.get_available_models()
        embed_model = None
        for m in models:
            if 'embed' in m.lower() or 'nomic' in m.lower():
                embed_model = m
                break
        if not embed_model and models:
            embed_model = models[0]
        if not embed_model:
            return None

        resp = requests.post(
            f"{OLLAMA_URL}/api/embed",
            json={"model": embed_model, "input": text},
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            # Ollama returns {"embeddings": [[...]]} for /api/embed
            embeddings = data.get("embeddings") or data.get("embedding")
            if embeddings:
                vec = embeddings[0] if isinstance(embeddings[0], list) else embeddings
                logger.debug(f"Ollama embedding: {len(vec)} dims via {embed_model}")
                return vec
    except Exception as e:
        logger.debug(f"Ollama embedding failed: {e}")
    return None


def _embed_gemini(text: str) -> Optional[List[float]]:
    """Try to get embeddings from Gemini."""
    try:
        import requests
        from backend.ai.providers import _get_key, GEMINI_API_URL

        api_key = _get_key("GEMINI_API_KEY")
        if not api_key:
            return None

        resp = requests.post(
            f"{GEMINI_API_URL}/text-embedding-004:embedContent",
            params={"key": api_key},
            json={"model": "models/text-embedding-004", "content": {"parts": [{"text": text}]}},
            timeout=15,
        )
        if resp.status_code == 200:
            vec = resp.json().get("embedding", {}).get("values", [])
            if vec:
                logger.debug(f"Gemini embedding: {len(vec)} dims")
                return vec
    except Exception as e:
        logger.debug(f"Gemini embedding failed: {e}")
    return None


# Simple TF-IDF fallback — no external dependencies beyond stdlib
_tfidf_vocab = {}

def _embed_tfidf(text: str, dim: int = 128) -> List[float]:
    """
    Simple hash-based bag-of-words embedding as last-resort fallback.
    Not great quality but works offline with zero dependencies.
    """
    import hashlib
    words = text.lower().split()
    vec = [0.0] * dim
    for word in words:
        h = int(hashlib.md5(word.encode()).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 7) % 2 == 0 else -1.0
        vec[idx] += sign
    # Normalize
    magnitude = sum(v * v for v in vec) ** 0.5
    if magnitude > 0:
        vec = [v / magnitude for v in vec]
    return vec


def get_embedding(text: str) -> List[float]:
    """
    Get a vector embedding for text. Tries providers in order:
    Ollama → Gemini → hash-based fallback.
    """
    if not text or not text.strip():
        return _embed_tfidf("")

    # Truncate very long text
    text = text[:2000]

    vec = _embed_ollama(text)
    if vec:
        return vec

    vec = _embed_gemini(text)
    if vec:
        return vec

    return _embed_tfidf(text)


def get_embedding_model_name() -> str:
    """Return which model is being used for embeddings."""
    try:
        from backend.ai.providers import OllamaProvider
        if OllamaProvider.is_available():
            models = OllamaProvider.get_available_models()
            for m in models:
                if 'embed' in m.lower() or 'nomic' in m.lower():
                    return f"ollama:{m}"
            if models:
                return f"ollama:{models[0]}"
    except Exception:
        pass

    try:
        from backend.ai.providers import _get_key
        if _get_key("GEMINI_API_KEY"):
            return "gemini:text-embedding-004"
    except Exception:
        pass

    return "tfidf-fallback"


def serialize_embedding(vec: List[float]) -> bytes:
    """Serialize a float list to compact bytes for SQLite BLOB storage."""
    return struct.pack(f'{len(vec)}f', *vec)


def deserialize_embedding(blob: bytes) -> List[float]:
    """Deserialize bytes back to float list."""
    count = len(blob) // 4
    return list(struct.unpack(f'{count}f', blob))


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(x * x for x in b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def embed_and_store(db, entity_type: str, entity_id: int, text: str):
    """Embed text and store in database. Convenience function."""
    try:
        vec = get_embedding(text)
        blob = serialize_embedding(vec)
        model = get_embedding_model_name()
        db.store_embedding(entity_type, entity_id, blob, model)
        logger.debug(f"Stored {entity_type}:{entity_id} embedding ({len(vec)} dims)")
    except Exception as e:
        logger.warning(f"Failed to embed {entity_type}:{entity_id}: {e}")
