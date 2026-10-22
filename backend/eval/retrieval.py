"""Retrieval modes compared by the evaluation harness.

All modes return production-shaped ``RetrievedPassage`` dicts, capped at
``TOP_K`` (3, as in production), so they can be dropped into the scorer.

- ``none``       no passages (LLM-only ablation)
- ``dense``      cosine similarity over FastEmbed vectors (what ChromaDB does today)
- ``bm25``       lexical BM25 over the same chunks
- ``hybrid``     reciprocal-rank fusion of dense and BM25
- ``dense_web``  dense, plus Tavily when the best similarity < WEB_AUGMENT_THRESHOLD
                 (production behaviour)
- ``hybrid_rerank``  hybrid candidates re-scored by an ONNX cross-encoder (needs fastembed >= 0.4)
"""
from __future__ import annotations

import re
from collections.abc import Sequence

import numpy as np
from rank_bm25 import BM25Okapi

from backend.agents.embeddings import embed_texts
from backend.agents.nodes.retriever import TOP_K, WEB_AUGMENT_THRESHOLD, _web_search
from backend.agents.state import RetrievedPassage
from backend.eval.corpus import Chunk, CorpusIndex

MODES = ("none", "dense", "bm25", "hybrid", "dense_web", "hybrid_rerank")
RRF_K = 60  # standard reciprocal-rank-fusion constant
CANDIDATES = 20  # depth each ranker contributes to the fusion
RERANK_POOL = 10  # fused candidates handed to the cross-encoder
RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"

_TOKEN = re.compile(r"[a-z0-9]+")


class _CrossEncoder:
    """Thin wrapper over fastembed's ONNX cross-encoder (needs fastembed >= 0.4)."""

    def __init__(self) -> None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        self._model = TextCrossEncoder(model_name=RERANK_MODEL)

    def rerank(self, query: str, docs: list[str]) -> list[float]:
        return [float(s) for s in self._model.rerank(query, docs)]


_cross_encoder_instance: _CrossEncoder | None = None


def _cross_encoder() -> _CrossEncoder:
    global _cross_encoder_instance
    if _cross_encoder_instance is None:
        _cross_encoder_instance = _CrossEncoder()
    return _cross_encoder_instance


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens (BM25 and token-overlap helpers share this)."""
    return _TOKEN.findall(text.lower())


def _passage(chunk: Chunk, score: float) -> RetrievedPassage:
    return RetrievedPassage(
        doc=chunk.doc,
        page=chunk.page,
        chunk=chunk.chunk,
        score=round(float(score), 4),
        text=chunk.text,
        source_url=chunk.source_url,
        web_url=chunk.web_url,
    )


def rrf_fuse(rankings: Sequence[Sequence[int]], k: int = RRF_K) -> list[tuple[int, float]]:
    """Fuse several best-first index rankings; returns ``(index, rrf_score)`` best first."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, idx in enumerate(ranking, start=1):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)


class EvalRetriever:
    """Runs any retrieval mode over a ``CorpusIndex``."""

    def __init__(self, index: CorpusIndex) -> None:
        self.index = index
        self._bm25 = BM25Okapi([tokenize(c.text) for c in index.chunks])

    def _dense_scores(self, claim: str) -> np.ndarray:
        q = np.asarray(embed_texts([claim])[0], dtype=np.float32)
        q /= max(float(np.linalg.norm(q)), 1e-12)
        return self.index.vectors @ q

    def _dense_rank(self, claim: str) -> tuple[list[int], np.ndarray]:
        sims = self._dense_scores(claim)
        return list(np.argsort(-sims)[:CANDIDATES]), sims

    def _bm25_rank(self, claim: str) -> list[int]:
        scores = self._bm25.get_scores(tokenize(claim))
        return list(np.argsort(-scores)[:CANDIDATES])

    def retrieve(self, claim: str, mode: str) -> list[RetrievedPassage]:
        """Return up to ``TOP_K`` passages for ``claim`` under ``mode``."""
        chunks = self.index.chunks
        if mode == "none":
            return []
        if mode in ("dense", "dense_web"):
            order, sims = self._dense_rank(claim)
            top = [_passage(chunks[i], max(0.0, float(sims[i]))) for i in order[:TOP_K]]
            if mode == "dense_web":
                best = max((p["score"] for p in top), default=0.0)
                if best < WEB_AUGMENT_THRESHOLD:
                    merged = top + _web_search(claim)
                    merged.sort(key=lambda p: p["score"], reverse=True)
                    top = merged[:TOP_K]
            return top
        if mode == "bm25":
            order = self._bm25_rank(claim)
            scores = self._bm25.get_scores(tokenize(claim))
            return [_passage(chunks[i], scores[i]) for i in order[:TOP_K]]
        if mode == "hybrid":
            dense_order, sims = self._dense_rank(claim)
            fused = rrf_fuse([dense_order, self._bm25_rank(claim)])
            # Keep the true cosine as the score so downstream thresholds stay meaningful.
            return [_passage(chunks[i], max(0.0, float(sims[i]))) for i, _ in fused[:TOP_K]]
        if mode == "hybrid_rerank":
            dense_order, sims = self._dense_rank(claim)
            pool = [i for i, _ in rrf_fuse([dense_order, self._bm25_rank(claim)])[:RERANK_POOL]]
            rr_scores = _cross_encoder().rerank(claim, [chunks[i].text for i in pool])
            ranked = sorted(zip(pool, rr_scores, strict=True), key=lambda t: t[1], reverse=True)[:TOP_K]
            return [_passage(chunks[i], max(0.0, float(sims[i]))) for i, _ in ranked]
        raise ValueError(f"Unknown retrieval mode {mode!r}; choose from {MODES}")
