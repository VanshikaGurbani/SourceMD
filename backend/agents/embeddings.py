"""Embedding helpers using FastEmbed (ONNX-based, low memory).

FastEmbed runs the model through ONNX Runtime instead of PyTorch. Measured peak
RSS of import + model load + one 64-text batch on Linux: ~247 MB vs ~526 MB for
sentence-transformers (scripts/bench_memory.py, results in the README). That
difference is what lets it fit in Render's 512 MB free tier.

The same model (all-MiniLM-L6-v2) is used so vectors are compatible with
existing ChromaDB chunks.
"""
from __future__ import annotations

from functools import lru_cache

from backend.config import get_settings


@lru_cache(maxsize=1)
def _get_model():
    """Return a cached FastEmbed TextEmbedding model."""
    from fastembed import TextEmbedding  # noqa: WPS433
    settings = get_settings()
    return TextEmbedding(model_name=settings.EMBEDDING_MODEL)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings and return plain Python float lists.

    ChromaDB expects plain lists, so we convert the numpy output explicitly.
    """
    model = _get_model()
    embeddings = list(model.embed(texts))
    return [e.tolist() for e in embeddings]
