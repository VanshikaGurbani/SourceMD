"""Compute trust quality metrics directly from pipeline output.

Replaces RAGAS (which requires a paid LLM judge and has Groq compatibility
issues) with two lightweight metrics computed from data already in hand:

- hallucination_rate: fraction of claims that are UNSUPPORTED or CONTRADICTED.
  0.0 = every claim is supported; 1.0 = everything is hallucinated.
  Stored in the ``ragas_faithfulness`` DB column.

- source_coverage: fraction of claims that have at least one retrieved passage
  with cosine similarity >= SOURCE_THRESHOLD (i.e. the corpus actually has
  relevant content for that claim).
  0.0 = no claim has a matching source; 1.0 = full corpus support.
  Stored in the ``ragas_context_precision`` DB column.
"""
from __future__ import annotations

from backend.agents.state import ScoredClaim

# A passage must reach this similarity score to count as "covering" its claim.
SOURCE_THRESHOLD = 0.40

_HALLUCINATED_VERDICTS = {"UNSUPPORTED", "CONTRADICTED"}


def evaluate_with_ragas(
    question: str,  # noqa: ARG001 — kept for API compatibility
    answer: str,    # noqa: ARG001
    scored_claims: list[ScoredClaim],
) -> dict[str, float | None]:
    """Return hallucination_rate and source_coverage for this evaluation.

    Both values are in [0.0, 1.0]. Returns None for both if there are no claims.
    The return keys use the legacy RAGAS names so the calling code and DB
    columns need no changes.
    """
    total = len(scored_claims)
    if total == 0:
        return {"faithfulness": None, "context_precision": None}

    # --- hallucination rate -------------------------------------------
    hallucinated = sum(
        1 for sc in scored_claims if sc.get("verdict", "") in _HALLUCINATED_VERDICTS
    )
    hallucination_rate = hallucinated / total

    # --- source coverage ---------------------------------------------
    covered = 0
    for sc in scored_claims:
        sources = sc.get("sources") or []
        best_score = max((float(s.get("score", 0.0)) for s in sources), default=0.0)
        if best_score >= SOURCE_THRESHOLD:
            covered += 1
    source_coverage = covered / total

    return {
        "faithfulness": round(hallucination_rate, 4),
        "context_precision": round(source_coverage, 4),
    }
