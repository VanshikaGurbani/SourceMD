"""The ChromaDB seed restores the corpus after the free-tier instance loses its data."""
from __future__ import annotations

import json

import chromadb
import numpy as np
import pytest

from backend.eval.corpus import build_chunks
from backend.ingestion.ingest import _chunk_id
from backend.ingestion.seed import CHUNKS_FILE, VECTORS_FILE, seed_if_empty


@pytest.fixture
def collection():
    client = chromadb.EphemeralClient()
    name = "seed_test"
    try:
        client.delete_collection(name)
    except Exception:  # noqa: BLE001
        pass
    return client.get_or_create_collection(name, metadata={"hnsw:space": "cosine"})


def test_seed_populates_an_empty_collection(collection):
    n = seed_if_empty(collection)
    assert n == collection.count() == 844
    vectors = np.load(VECTORS_FILE)
    result = collection.query(query_embeddings=[vectors[10].tolist()], n_results=1, include=["metadatas"])
    first = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))[10]
    assert result["ids"][0][0] == first["id"]
    assert result["metadatas"][0][0]["doc"] == first["metadata"]["doc"]


def test_seed_does_nothing_when_data_exists(collection):
    seed_if_empty(collection)
    assert seed_if_empty(collection) == 0
    assert collection.count() == 844


def test_seed_matches_the_cached_pdfs():
    """Fails if the PDFs or chunking change without re-exporting the seed."""
    seeded = {c["id"] for c in json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))}
    current = {_chunk_id(c.doc, c.page, c.chunk, c.text) for c in build_chunks()}
    assert seeded == current
    assert len(np.load(VECTORS_FILE)) == len(seeded)
