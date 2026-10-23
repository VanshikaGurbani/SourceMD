"""Retriever node: dense path, hybrid path, and the web-augmentation threshold."""
from __future__ import annotations

import pytest

from backend.agents.hybrid import Bm25Index, rrf_fuse, tokenize
from backend.agents.nodes import retriever

CHUNKS = [
    ("Offer metformin and an SGLT-2 inhibitor to adults with type 2 diabetes.", "NG28", 29, 0),
    ("Measure blood pressure in both arms when considering hypertension.", "NG136", 7, 0),
    ("Atorvastatin 20 mg is offered for primary prevention of CVD.", "NG238", 18, 0),
    ("Back blows and abdominal thrusts for severe choking.", "AHA", 13, 0),
]


class FakeCollection:
    """Minimal ChromaDB stand-in: dense ranking is fixed per test."""

    def __init__(self, dense_order: list[int], distances: list[float]):
        self.dense_order, self.distances = dense_order, distances

    def count(self):
        return len(CHUNKS)

    def get(self, include=None):
        return {
            "documents": [c[0] for c in CHUNKS],
            "metadatas": [{"doc": c[1], "page": c[2], "chunk": c[3]} for c in CHUNKS],
        }

    def query(self, query_embeddings, n_results, include):
        idx = self.dense_order[:n_results]
        return {
            "documents": [[CHUNKS[i][0] for i in idx]],
            "metadatas": [[{"doc": CHUNKS[i][1], "page": CHUNKS[i][2], "chunk": CHUNKS[i][3]} for i in idx]],
            "distances": [self.distances[: len(idx)]],
        }


@pytest.fixture
def patched(monkeypatch):
    def apply(collection, hybrid: bool):
        retriever._bm25_corpus.cache_clear()
        monkeypatch.setattr(retriever, "get_guidelines_collection", lambda: collection)
        monkeypatch.setattr(retriever, "embed_texts", lambda texts: [[0.0] * 3 for _ in texts])
        monkeypatch.setattr(retriever, "_web_search", lambda claim: [])

        class S:
            HYBRID_RETRIEVAL = hybrid
            TAVILY_API_KEY = ""

        monkeypatch.setattr(retriever, "get_settings", lambda: S())

    yield apply
    retriever._bm25_corpus.cache_clear()


def test_dense_path_uses_chroma_order_and_cosine(patched):
    patched(FakeCollection([1, 0, 2], [0.2, 0.3, 0.4]), hybrid=False)
    out = retriever.retrieve_passages({"claims": ["claim"]})["retrieved"]["claim"]
    assert [p["doc"] for p in out] == ["NG136", "NG28", "NG238"]
    assert out[0]["score"] == pytest.approx(0.8)


def test_hybrid_rescues_a_lexical_match_the_dense_ranker_missed(patched):
    # Dense ranks the diabetes chunk last, but the query shares its exact words.
    patched(FakeCollection([1, 2, 3, 0], [0.3, 0.35, 0.4, 0.45]), hybrid=True)
    claim = "Metformin and an SGLT-2 inhibitor are offered for type 2 diabetes"
    dense_only = [p["doc"] for p in retriever._dense_passages(FakeCollection([1, 2, 3, 0], [0.3, 0.35, 0.4, 0.45]), [0.0], 3)]
    assert "NG28" not in dense_only
    out = retriever.retrieve_passages({"claims": [claim]})["retrieved"][claim]
    ng28 = next(p for p in out if p["doc"] == "NG28")  # rescued into the top-3 by BM25
    assert len(out) == retriever.TOP_K
    assert ng28["score"] == pytest.approx(0.55)  # true cosine kept, not the fusion score


def test_empty_claims(patched):
    patched(FakeCollection([], []), hybrid=True)
    assert retriever.retrieve_passages({"claims": []}) == {"retrieved": {}}


def test_fusion_helpers():
    assert tokenize("Offer SGLT-2, 20 mg!") == ["offer", "sglt", "2", "20", "mg"]
    assert [i for i, _ in rrf_fuse([[1, 2], [2, 3]])][0] == 2
    idx = Bm25Index([c[0] for c in CHUNKS])
    assert idx.top("choking back blows", 1) == [3]
