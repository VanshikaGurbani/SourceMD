"""BM25 + dense reciprocal-rank fusion helpers shared by the app and the eval harness."""
from __future__ import annotations

import re
from collections.abc import Sequence

RRF_K = 60  # standard reciprocal-rank-fusion constant
_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens used for BM25 and token-overlap checks."""
    return _TOKEN.findall(text.lower())


def rrf_fuse(rankings: Sequence[Sequence[int]], k: int = RRF_K) -> list[tuple[int, float]]:
    """Fuse several best-first index rankings; returns ``(index, rrf_score)`` best first."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, idx in enumerate(ranking, start=1):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)


class Bm25Index:
    """BM25 over a fixed list of chunk texts (built once from the vector store)."""

    def __init__(self, texts: list[str]) -> None:
        from rank_bm25 import BM25Okapi

        self.texts = texts
        self._bm25 = BM25Okapi([tokenize(t) for t in texts])

    def top(self, query: str, n: int) -> list[int]:
        """Indices of the ``n`` best chunks for ``query``, best first."""
        scores = self._bm25.get_scores(tokenize(query))
        return sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n]
