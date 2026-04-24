"""Shared state object that flows through the LangGraph pipeline."""
from __future__ import annotations

from typing import Any, TypedDict


class RetrievedPassage(TypedDict):
    """One passage returned by the ChromaDB retriever."""

    doc: str
    page: int
    chunk: int
    score: float
    text: str
    source_url: str  # direct PDF download URL
    web_url: str     # canonical guideline webpage URL shown in citations


class ScoredClaim(TypedDict):
    """A claim after the scorer node has labelled it."""

    text: str
    verdict: str  # SUPPORTED | UNSUPPORTED | CONTRADICTED
    confidence: float
    rationale: str
    sources: list[RetrievedPassage]


class PipelineState(TypedDict, total=False):
    """State container passed between LangGraph nodes."""

    question: str
    ai_answer: str
    claims: list[str]
    retrieved: dict[str, list[RetrievedPassage]]  # keyed by claim text
    scored_claims: list[ScoredClaim]
    trust_score: float
    corrected_answer: str
    follow_up_questions: list[str]
    raw: dict[str, Any]
