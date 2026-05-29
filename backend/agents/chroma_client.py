"""Thin wrapper around the ChromaDB HTTP client."""
from __future__ import annotations

from functools import lru_cache

import chromadb
from chromadb.api.models.Collection import Collection

from backend.config import get_settings


@lru_cache(maxsize=1)
def get_chroma_client() -> chromadb.HttpClient:
    """Return a cached ChromaDB HTTP client configured from settings.

    Uses SSL automatically when port is 443 (Render / production deployments).
    Ensures the default tenant and database exist before returning the client.
    """
    settings = get_settings()
    ssl = settings.CHROMA_PORT == 443

    # Ensure default tenant/database exist (required on fresh remote instances).
    try:
        admin = chromadb.AdminClient(chromadb.Settings(
            chroma_api_impl="chromadb.api.fastapi.FastAPI",
            chroma_server_host=settings.CHROMA_HOST,
            chroma_server_http_port=settings.CHROMA_PORT,
            chroma_server_ssl_enabled=ssl,
        ))
        try:
            admin.get_tenant("default_tenant")
        except Exception:
            admin.create_tenant("default_tenant")
        try:
            admin.get_database("default_database", tenant="default_tenant")
        except Exception:
            admin.create_database("default_database", tenant="default_tenant")
    except Exception:  # noqa: BLE001
        pass  # Best-effort — HttpClient will surface any real errors

    return chromadb.HttpClient(
        host=settings.CHROMA_HOST,
        port=settings.CHROMA_PORT,
        ssl=ssl,
    )


def get_guidelines_collection() -> Collection:
    """Return (creating if needed) the guidelines collection used for RAG."""
    settings = get_settings()
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=settings.CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )
