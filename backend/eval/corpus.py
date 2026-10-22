"""Local, server-free index of the guideline corpus for evaluation.

Chunks the cached PDFs with exactly the production chunker (800 chars, 100
overlap, per page) and embeds them with the production FastEmbed model, so
retrieval here matches what ChromaDB serves in production without needing a
ChromaDB server. The embedding matrix is cached on disk (gitignored).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from backend.config import get_settings
from backend.ingestion.ingest import CACHE_DIR, CHUNK_OVERLAP, CHUNK_SIZE, _chunk_text, _extract_pages
from backend.ingestion.sources import SOURCES

INDEX_DIR = Path(__file__).parent / "cache"


@dataclass(frozen=True)
class Chunk:
    """One indexed chunk plus its provenance."""

    doc: str
    page: int
    chunk: int
    text: str
    source_url: str
    web_url: str


def load_pages() -> dict[str, list[tuple[int, str]]]:
    """Return ``{doc_name: [(page_number, page_text), ...]}`` for every cached PDF."""
    pages: dict[str, list[tuple[int, str]]] = {}
    for src in SOURCES:
        path = CACHE_DIR / f"{src['name']}.pdf"
        if path.exists():
            pages[src["name"]] = _extract_pages(path)
    return pages


def build_chunks() -> list[Chunk]:
    """Chunk every cached PDF the same way production ingestion does."""
    chunks: list[Chunk] = []
    for src in SOURCES:
        path = CACHE_DIR / f"{src['name']}.pdf"
        if not path.exists():
            continue
        for page_number, page_text in _extract_pages(path):
            for idx, text in enumerate(_chunk_text(page_text)):
                chunks.append(
                    Chunk(src["name"], page_number, idx, text, src["url"], src["web_url"])
                )
    return chunks


def _fingerprint(model: str) -> str:
    h = hashlib.sha256()
    h.update(f"{model}|{CHUNK_SIZE}|{CHUNK_OVERLAP}".encode())
    for src in SOURCES:
        path = CACHE_DIR / f"{src['name']}.pdf"
        if path.exists():
            h.update(hashlib.sha256(path.read_bytes()).digest())
    return h.hexdigest()[:16]


class CorpusIndex:
    """Chunks + L2-normalised embeddings, loaded from cache or built on demand."""

    def __init__(self, chunks: list[Chunk], vectors: np.ndarray) -> None:
        self.chunks = chunks
        self.vectors = vectors

    @classmethod
    def load(cls, *, rebuild: bool = False) -> CorpusIndex:
        """Load the cached index, rebuilding when PDFs, model or chunking changed."""
        from backend.agents.embeddings import embed_texts

        model = get_settings().EMBEDDING_MODEL
        fp = _fingerprint(model)
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        meta_path = INDEX_DIR / "corpus_chunks.json"
        vec_path = INDEX_DIR / "corpus_vectors.npy"

        if not rebuild and meta_path.exists() and vec_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("fingerprint") == fp:
                chunks = [Chunk(**c) for c in meta["chunks"]]
                return cls(chunks, np.load(vec_path))

        chunks = build_chunks()
        vecs = []
        for i in range(0, len(chunks), 64):
            vecs.extend(embed_texts([c.text for c in chunks[i : i + 64]]))
        matrix = np.asarray(vecs, dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        matrix = matrix / np.clip(norms, 1e-12, None)
        meta_path.write_text(
            json.dumps(
                {"fingerprint": fp, "chunks": [c.__dict__ for c in chunks]},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        np.save(vec_path, matrix)
        return cls(chunks, matrix)
