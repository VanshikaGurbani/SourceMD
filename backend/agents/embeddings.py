"""Embedding helpers using FastEmbed (ONNX-based, low memory).

FastEmbed uses quantized ONNX models instead of full PyTorch, keeping RAM
usage ~100 MB vs ~300 MB for sentence-transformers. This fits comfortably
within Render's 512 MB free-tier limit.

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
