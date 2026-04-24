"""LangGraph node: for each claim retrieve passages from ChromaDB and optionally Tavily."""
from __future__ import annotations

from backend.agents.chroma_client import get_guidelines_collection
from backend.agents.embeddings import embed_texts
from backend.agents.state import PipelineState, RetrievedPassage
from backend.config import get_settings

TOP_K = 3
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
    if not settings.TAVILY_API_KEY:
        return []
    try:
        from tavily import TavilyClient  # noqa: WPS433
        client = TavilyClient(api_key=settings.TAVILY_API_KEY)
        response = client.search(
            query=f"medical guideline {claim}",
            search_depth="basic",
            include_domains=TRUSTED_DOMAINS,
            max_results=2,
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
    except Exception:  # noqa: BLE001
        return []


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
    vectors = embed_texts(claims)

    out: dict[str, list[RetrievedPassage]] = {}
    for claim, vector in zip(claims, vectors):
        result = collection.query(
            query_embeddings=[vector],
            n_results=TOP_K,
            include=["documents", "metadatas", "distances"],
        )
        passages: list[RetrievedPassage] = []
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        dists = (result.get("distances") or [[]])[0]

        for text, meta, dist in zip(docs, metas, dists):
            meta = meta or {}
            similarity = max(0.0, 1.0 - float(dist))
            passages.append(
                RetrievedPassage(
                    doc=str(meta.get("doc", "unknown")),
                    page=int(meta.get("page", 0)),
                    chunk=int(meta.get("chunk", 0)),
                    score=round(similarity, 4),
                    text=text or "",
                    source_url=str(meta.get("source_url", "")),
                    web_url=str(meta.get("web_url", "")),
                )
            )

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
