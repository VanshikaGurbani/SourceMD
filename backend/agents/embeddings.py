"""Embedding helpers — local model for dev, HF Inference API for production.

When HF_TOKEN is set (Render / production), embeddings are computed via the
HuggingFace Inference API so the 300 MB sentence-transformers model is never
loaded into the container, keeping memory well under the 512 MB free-tier cap.

When HF_TOKEN is absent (local Docker Compose), the original local
SentenceTransformer is used — no behaviour change for local development.
"""
from __future__ import annotations

import os
from functools import lru_cache

from backend.config import get_settings


# ---------------------------------------------------------------------------
# Local path (no HF_TOKEN — used in Docker Compose dev)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_local_model():
    from sentence_transformers import SentenceTransformer  # noqa: WPS433
    settings = get_settings()
    return SentenceTransformer(settings.EMBEDDING_MODEL)


def _embed_local(texts: list[str]) -> list[list[float]]:
    model = _get_local_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]


# ---------------------------------------------------------------------------
# Remote path (HF_TOKEN set — used on Render free tier)
# ---------------------------------------------------------------------------

def _embed_hf_api(texts: list[str]) -> list[list[float]]:
    """Call the HuggingFace Inference API to embed texts.

    Uses the same all-MiniLM-L6-v2 model so vectors are compatible with
    chunks already stored in ChromaDB.
    """
    import httpx  # noqa: WPS433

    settings = get_settings()
    token = os.environ.get("HF_TOKEN", "")
    url = f"https://api-inference.huggingface.co/models/{settings.EMBEDDING_MODEL}"
    headers = {"Authorization": f"Bearer {token}"}

    results: list[list[float]] = []
    # HF API has a payload size limit — batch in groups of 64.
    batch_size = 64
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        resp = httpx.post(url, headers=headers, json={"inputs": batch}, timeout=60.0)
        resp.raise_for_status()
        data = resp.json()
        # Response shape: list of embedding vectors
        results.extend(data)
    return results


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings and return plain Python float lists.

    Routes to the HF Inference API when HF_TOKEN is set, otherwise uses the
    local SentenceTransformer model (Docker Compose dev environment).
    """
    if os.environ.get("HF_TOKEN"):
        return _embed_hf_api(texts)
    return _embed_local(texts)
