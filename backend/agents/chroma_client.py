"""Thin wrapper around the ChromaDB HTTP client."""
from __future__ import annotations

import time
from functools import lru_cache

import chromadb
from chromadb.api.models.Collection import Collection

from backend.config import get_settings

# Free-tier hosts spin down when idle; the first request can hit a 429/refused
# connection while the service wakes up, so we retry with backoff (~60s total).
CONNECT_RETRIES = 5
BACKOFF_SECONDS = [2, 5, 10, 20, 30]


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

    last_error: Exception | None = None
    for attempt in range(CONNECT_RETRIES):
        try:
            return chromadb.HttpClient(
                host=settings.CHROMA_HOST,
                port=settings.CHROMA_PORT,
                ssl=ssl,
            )
        except Exception as exc:  # noqa: BLE001 — client raises bare ValueError on 429s
            last_error = exc
            if attempt < CONNECT_RETRIES - 1:
                time.sleep(BACKOFF_SECONDS[attempt])
    raise RuntimeError(
        f"Could not connect to ChromaDB after {CONNECT_RETRIES} attempts: {last_error}"
    ) from last_error


def get_guidelines_collection() -> Collection:
    """Return (creating if needed) the guidelines collection used for RAG."""
    settings = get_settings()
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=settings.CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )
