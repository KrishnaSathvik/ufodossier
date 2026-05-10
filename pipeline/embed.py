"""
ufodossier // embeddings

Uses Voyage (voyage-3) by default — Anthropic's recommended embedder.
Falls back to OpenAI text-embedding-3-small if VOYAGE_API_KEY missing.

Voyage-3 outputs 1024 dims; we zero-pad to 1536 to match the DB schema
so either provider works with the same vector(1536) column.
"""
from __future__ import annotations

import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

VECTOR_DIM = 1536  # DB schema dimension
MAX_RETRIES = 8
CALL_DELAY = 1.5  # seconds between calls to stay under free-tier RPM limits
_last_call_time = 0.0


def embed_text(text: str) -> list[float]:
    """Embed a single text. For multiple texts, use embed_batch() instead."""
    return embed_batch([text])[0]


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed multiple texts in a single API call. Much more efficient than
    calling embed_text() in a loop since it uses 1 API call per batch instead
    of 1 per text, drastically reducing rate-limit pressure."""
    global _last_call_time

    if not texts:
        return []

    # rate-limit ourselves to avoid 429s on free tier
    elapsed = time.time() - _last_call_time
    if elapsed < CALL_DELAY:
        time.sleep(CALL_DELAY - elapsed)

    if os.environ.get("VOYAGE_API_KEY"):
        vecs = _voyage_batch(texts)
    else:
        vecs = _openai_batch(texts)

    _last_call_time = time.time()

    # pad each vector to match DB vector(1536) if model returns fewer dimensions
    for vec in vecs:
        if len(vec) < VECTOR_DIM:
            vec.extend([0.0] * (VECTOR_DIM - len(vec)))
    return vecs


def _voyage_batch(texts: list[str]) -> list[list[float]]:
    """Voyage supports up to 128 inputs per call. We send all at once (capped at 128)."""
    truncated = [t[:8000] for t in texts]
    for attempt in range(MAX_RETRIES):
        r = httpx.post(
            "https://api.voyageai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {os.environ['VOYAGE_API_KEY']}"},
            json={"input": truncated, "model": "voyage-3", "output_dimension": 1024},
            timeout=60.0,
        )
        if r.status_code == 429:
            wait = 5 * (2 ** attempt)  # 5, 10, 20, 40, 80, 160, 320, 640
            logger.warning("voyage rate limit, retrying in %ds (attempt %d/%d)", wait, attempt + 1, MAX_RETRIES)
            time.sleep(wait)
            continue
        r.raise_for_status()
        data = r.json()["data"]
        # API returns items sorted by index, but let's be safe
        data.sort(key=lambda d: d["index"])
        return [d["embedding"] for d in data]
    r.raise_for_status()  # raise on final failure
    return []  # unreachable


def _openai_batch(texts: list[str]) -> list[list[float]]:
    truncated = [t[:8000] for t in texts]
    for attempt in range(MAX_RETRIES):
        r = httpx.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
            json={"input": truncated, "model": "text-embedding-3-small"},
            timeout=60.0,
        )
        if r.status_code == 429:
            wait = 5 * (2 ** attempt)
            logger.warning("openai rate limit, retrying in %ds (attempt %d/%d)", wait, attempt + 1, MAX_RETRIES)
            time.sleep(wait)
            continue
        r.raise_for_status()
        data = r.json()["data"]
        data.sort(key=lambda d: d["index"])
        return [d["embedding"] for d in data]
    r.raise_for_status()
    return []
