"""LangGraph node: for each claim retrieve passages from ChromaDB and optionally Tavily."""
from __future__ import annotations

from functools import lru_cache

from backend.agents.call_cache import CacheMiss, cache_mode, cached_call
from backend.agents.chroma_client import get_guidelines_collection
from backend.agents.embeddings import embed_texts
from backend.agents.hybrid import Bm25Index, rrf_fuse
from backend.agents.state import PipelineState, RetrievedPassage
from backend.config import get_settings
from backend.ingestion.seed import seed_if_empty

TOP_K = 3
CANDIDATES = 20  # depth each ranker contributes to hybrid fusion
# If the best local similarity is below this threshold we supplement with web results.
WEB_AUGMENT_THRESHOLD = 0.35
# Trusted medical guideline domains searched by Tavily.
TRUSTED_DOMAINS = [
    "who.int",
    "nice.org.uk",
    "heart.org",
    "nih.gov",
    "cdc.gov",
    "pubmed.ncbi.nlm.nih.gov",
    "bmj.com",
    "thelancet.com",
    "nejm.org",
    "uptodate.com",
    "mayoclinic.org",
]


def _web_search(claim: str) -> list[RetrievedPassage]:
    """Search live medical guideline sites via Tavily for passages about ``claim``.

    Returns an empty list if TAVILY_API_KEY is not configured or the search fails.
    Each returned passage has ``page=0``, ``chunk=-1`` to signal a web result.
    """
    settings = get_settings()
    if not settings.TAVILY_API_KEY and cache_mode() not in ("replay", "count"):
        return []
    query = f"medical guideline {claim}"

    def _search() -> dict:
        from tavily import TavilyClient  # noqa: WPS433
        client = TavilyClient(api_key=settings.TAVILY_API_KEY)
        return client.search(
            query=query,
            search_depth="basic",
            include_domains=TRUSTED_DOMAINS,
            max_results=2,
        )

    try:
        response = cached_call(
            "tavily",
            {"query": query, "domains": TRUSTED_DOMAINS, "max_results": 2},
            _search,
            placeholder={"results": []},
        )
        passages: list[RetrievedPassage] = []
        for r in response.get("results", []):
            url = r.get("url", "")
            passages.append(
                RetrievedPassage(
                    doc=r.get("title", "Web source")[:80],
                    page=0,
                    chunk=-1,
                    score=round(float(r.get("score", 0.5)), 4),
                    text=(r.get("content") or "").strip()[:1200],
                    source_url=url,
                    web_url=url,
                )
            )
        return passages
    except CacheMiss:
        raise  # a replay gap must be visible, not silently "no web results"
    except Exception:  # noqa: BLE001
        return []


def _dense_passages(collection, vector: list[float], n: int) -> list[RetrievedPassage]:
    """Top-``n`` passages by cosine similarity from ChromaDB."""
    result = collection.query(
        query_embeddings=[vector],
        n_results=n,
        include=["documents", "metadatas", "distances"],
    )
    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    dists = (result.get("distances") or [[]])[0]
    passages: list[RetrievedPassage] = []
    for text, meta, dist in zip(docs, metas, dists, strict=False):
        meta = meta or {}
        passages.append(
            RetrievedPassage(
                doc=str(meta.get("doc", "unknown")),
                page=int(meta.get("page", 0)),
                chunk=int(meta.get("chunk", 0)),
                score=round(max(0.0, 1.0 - float(dist)), 4),
                text=text or "",
                source_url=str(meta.get("source_url", "")),
                web_url=str(meta.get("web_url", "")),
            )
        )
    return passages


@lru_cache(maxsize=1)
def _bm25_corpus() -> tuple[Bm25Index, list[tuple[str, str, int, int, str, str]]]:
    """Build the BM25 index once from every chunk in the collection (~800 chunks)."""
    data = get_guidelines_collection().get(include=["documents", "metadatas"])
    texts = list(data.get("documents") or [])
    metas = list(data.get("metadatas") or [])
    rows = [
        (
            text or "",
            str((m or {}).get("doc", "unknown")),
            int((m or {}).get("page", 0)),
            int((m or {}).get("chunk", 0)),
            str((m or {}).get("source_url", "")),
            str((m or {}).get("web_url", "")),
        )
        for text, m in zip(texts, metas, strict=False)
    ]
    return Bm25Index([r[0] for r in rows]), rows


def _hybrid_passages(collection, claim: str, vector: list[float]) -> list[RetrievedPassage]:
    """BM25 + dense reciprocal-rank fusion (see docs/EVAL_RESULTS.md for the measured gain).

    Each passage keeps its true cosine similarity (0.0 if the dense ranker did not
    return it) so the web-augmentation threshold keeps its meaning.
    """
    index, rows = _bm25_corpus()
    key_to_pos = {(r[1], r[2], r[3]): i for i, r in enumerate(rows)}
    dense = _dense_passages(collection, vector, CANDIDATES)
    dense_pos = [key_to_pos[(p["doc"], p["page"], p["chunk"])] for p in dense if (p["doc"], p["page"], p["chunk"]) in key_to_pos]
    sim_by_pos = {key_to_pos[(p["doc"], p["page"], p["chunk"])]: p["score"] for p in dense if (p["doc"], p["page"], p["chunk"]) in key_to_pos}
    fused = rrf_fuse([dense_pos, index.top(claim, CANDIDATES)])[:TOP_K]
    out: list[RetrievedPassage] = []
    for pos, _ in fused:
        text, doc, page, chunk, source_url, web_url = rows[pos]
        out.append(
            RetrievedPassage(
                doc=doc, page=page, chunk=chunk, score=sim_by_pos.get(pos, 0.0),
                text=text, source_url=source_url, web_url=web_url,
            )
        )
    return out

def retrieve_passages(state: PipelineState) -> PipelineState:
    """Query ChromaDB for each claim; augment with Tavily when local similarity is low.

    Writes ``state['retrieved']`` as a dict mapping each claim string to a
    combined list of local + web ``RetrievedPassage`` entries, capped at TOP_K
    total results per claim.
    """
    claims = state.get("claims", [])
    if not claims:
        return {"retrieved": {}}

    collection = get_guidelines_collection()
    # The free-tier Chroma instance comes back empty after it spins down; restore it from the seed files.
    seed_if_empty(collection)
    vectors = embed_texts(claims)

    use_hybrid = get_settings().HYBRID_RETRIEVAL
    out: dict[str, list[RetrievedPassage]] = {}
    for claim, vector in zip(claims, vectors, strict=True):
        if use_hybrid:
            passages = _hybrid_passages(collection, claim, vector)
        else:
            passages = _dense_passages(collection, vector, TOP_K)
        # Augment with live web results when local corpus has weak signal.
        best_local_score = max((p["score"] for p in passages), default=0.0)
        if best_local_score < WEB_AUGMENT_THRESHOLD:
            web_passages = _web_search(claim)
            # Merge: keep top local results + web results, sorted by score.
            combined = passages + web_passages
            combined.sort(key=lambda p: p["score"], reverse=True)
            passages = combined[:TOP_K]

        out[claim] = passages

    return {"retrieved": out}

