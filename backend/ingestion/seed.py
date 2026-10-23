"""Reload the guideline corpus into ChromaDB from precomputed vectors.

The free-tier ChromaDB instance keeps its data on an ephemeral disk, so it comes
back empty whenever the service spins down. ``seed_if_empty`` restores the
collection from ``backend/ingestion/seed/`` (chunk text, metadata and the
embedding vectors, produced by ``python -m backend.ingestion.seed --export``),
which needs no embedding model and no PDF parsing, so it is fast and light enough
for the 512 MB backend.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

SEED_DIR = Path(__file__).parent / "seed"
CHUNKS_FILE = SEED_DIR / "chunks.json"
VECTORS_FILE = SEED_DIR / "vectors.npy"
BATCH = 200


def seed_if_empty(collection) -> int:
    """Populate ``collection`` from the seed files when it has no documents.

    Returns the number of chunks upserted (0 if the collection already had data
    or no seed files are present).
    """
    if collection.count() > 0 or not (CHUNKS_FILE.exists() and VECTORS_FILE.exists()):
        return 0
    chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
    vectors = np.load(VECTORS_FILE)
    if len(chunks) != len(vectors):
        raise RuntimeError("Seed files are inconsistent: chunk and vector counts differ")
    for i in range(0, len(chunks), BATCH):
        part = chunks[i : i + BATCH]
        collection.upsert(
            ids=[c["id"] for c in part],
            documents=[c["text"] for c in part],
            metadatas=[c["metadata"] for c in part],
            embeddings=vectors[i : i + BATCH].tolist(),
        )
    return len(chunks)


def export_seed() -> int:
    """Write the seed files from the cached PDFs (embeds once with the production model)."""
    from backend.eval.corpus import CorpusIndex
    from backend.ingestion.ingest import _chunk_id
    from backend.ingestion.sources import SOURCES

    tags = {s["name"]: s["tag"] for s in SOURCES}
    index = CorpusIndex.load(rebuild=True)
    chunks = [
        {
            "id": _chunk_id(c.doc, c.page, c.chunk, c.text),
            "text": c.text,
            "metadata": {
                "doc": c.doc,
                "page": c.page,
                "chunk": c.chunk,
                "tag": tags[c.doc],
                "source_url": c.source_url,
                "web_url": c.web_url,
            },
        }
        for c in index.chunks
    ]
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    CHUNKS_FILE.write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    np.save(VECTORS_FILE, index.vectors.astype(np.float32))
    return len(chunks)


if __name__ == "__main__":
    import sys

    if "--export" in sys.argv:
        print(f"Exported {export_seed()} chunks to {SEED_DIR}")
    else:
        from backend.agents.chroma_client import get_guidelines_collection

        print(f"Seeded {seed_if_empty(get_guidelines_collection())} chunks")
