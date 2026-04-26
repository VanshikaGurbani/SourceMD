"""Pydantic schemas for evaluation and claim endpoints."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EvaluateRequest(BaseModel):
    """Request body for POST /evaluate."""

    question: str = Field(min_length=3, max_length=4000)
    ai_answer: str = Field(min_length=3, max_length=10000)


class SourceCitation(BaseModel):
    """A single retrieved passage cited as evidence for a claim."""

    doc: str
    page: int
    chunk: int
    score: float
    text: str
    source_url: str = ""
    web_url: str = ""


class ClaimOut(BaseModel):
    """Scoring result for one extracted claim."""

    id: int
    text: str
    verdict: str
    confidence: float
    rationale: str
    sources: list[dict[str, Any]]

    class Config:
        from_attributes = True


class EvaluationOut(BaseModel):
    """Full trust report for one evaluation."""

    id: int
    question: str
    ai_answer: str
    trust_score: float
    ragas_faithfulness: float | None
    ragas_context_precision: float | None
    corrected_answer: str
    follow_up_questions: list[str] = []
    created_at: datetime
    claims: list[ClaimOut]

    class Config:
        from_attributes = True


class EvaluationListItem(BaseModel):
    """Compact row for the local history list."""

    id: int
    question: str
    trust_score: float
    created_at: str
