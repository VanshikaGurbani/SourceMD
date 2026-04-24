"""Shared SentenceTransformer loader used by ingestion and retrieval."""
from __future__ import annotations

from functools import lru_cache

from sentence_transformers import SentenceTransformer

from backend.config import get_settings


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """Return a cached SentenceTransformer instance.

    The model is downloaded on first call (~80 MB for all-MiniLM-L6-v2) and
    reused for the lifetime of the process.
    """
    settings = get_settings()
    return SentenceTransformer(settings.EMBEDDING_MODEL)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings and return plain Python float lists.

    ChromaDB expects plain lists, so we convert the numpy output explicitly.
    """
    model = get_embedding_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]
