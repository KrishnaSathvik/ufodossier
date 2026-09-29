"""
ufodossier // embeddings

The incident index is Voyage voyage-3, 1024 dimensions, zero-padded to 1536.
OpenAI embeddings are a different vector space. This module never switches to
them, even when the Voyage call fails or the Voyage key is missing.
"""
from __future__ import annotations

import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

VECTOR_DIM = 1536  # DB schema dimension
VOYAGE_DIM = 1024
MAX_RETRIES = 8
CALL_DELAY = 1.5  # seconds between calls to stay under free-tier RPM limits
_last_call_time = 0.0


def resolve_embedding() -> tuple[str, str]:
    provider = (os.environ.get("EMBEDDING_PROVIDER") or "voyage").strip().lower()
    model = (os.environ.get("EMBEDDING_MODEL") or "voyage-3").strip()
    if provider != "voyage" or model != "voyage-3":
        raise RuntimeError(
            f"EMBEDDING_PROVIDER={provider} EMBEDDING_MODEL={model} does not match the voyage-3 index. "
            "OpenAI embeddings will not be used as a fallback."
        )
    if not os.environ.get("VOYAGE_API_KEY"):
        raise RuntimeError("VOYAGE_API_KEY is missing. Retrieval will not switch to OpenAI embeddings.")
    return provider, model


def embed_text(text: str) -> list[float]:
    """Embed a single text. For multiple texts, use embed_batch() instead."""
    return embed_batch([text])[0]


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed texts with voyage-3. Raises if Voyage is unavailable."""
    global _last_call_time
    if not texts:
        return []
    resolve_embedding()
    vectors: list[list[float]] = []
    for start in range(0, len(texts), 128):
        elapsed = time.time() - _last_call_time
        if elapsed < CALL_DELAY:
            time.sleep(CALL_DELAY - elapsed)
        chunk = _voyage_batch(texts[start : start + 128])
        _last_call_time = time.time()
        vectors.extend(chunk)
    for vec in vectors:
        if len(vec) != VOYAGE_DIM:
            raise RuntimeError(f"voyage-3 returned {len(vec)} dimensions, expected {VOYAGE_DIM}")
        vec.extend([0.0] * (VECTOR_DIM - len(vec)))
    return vectors


def _voyage_batch(texts: list[str]) -> list[list[float]]:
    truncated = [t[:8000] for t in texts]
    response = None
    for attempt in range(MAX_RETRIES):
        response = httpx.post(
            "https://api.voyageai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {os.environ['VOYAGE_API_KEY']}"},
            json={"input": truncated, "model": "voyage-3", "output_dimension": VOYAGE_DIM},
            timeout=60.0,
        )
        if response.status_code == 429:
            wait = 5 * (2 ** attempt)
            logger.warning("voyage rate limit, retrying in %ds (attempt %d/%d)", wait, attempt + 1, MAX_RETRIES)
            time.sleep(wait)
            continue
        if response.status_code >= 400:
            raise RuntimeError(
                f"Voyage embeddings failed ({response.status_code}). Not switching providers. {response.text[:240]}"
            )
        data = response.json()["data"]
        data.sort(key=lambda item: item["index"])
        return [item["embedding"] for item in data]
    raise RuntimeError("Voyage embeddings failed after retries. Not switching providers.")
