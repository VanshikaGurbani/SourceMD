"""Thin wrapper around the ChromaDB HTTP client."""
from __future__ import annotations

from functools import lru_cache

import chromadb
from chromadb.api.models.Collection import Collection

from backend.config import get_settings


@lru_cache(maxsize=1)
def get_chroma_client() -> chromadb.HttpClient:
    """Return a cached ChromaDB HTTP client configured from settings."""
    settings = get_settings()
    return chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)


def get_guidelines_collection() -> Collection:
    """Return (creating if needed) the guidelines collection used for RAG."""
    settings = get_settings()
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=settings.CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )
