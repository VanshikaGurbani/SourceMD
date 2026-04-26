"""Public /history routes — no auth required."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.db.base import get_db
from backend.db.models import Claim, Evaluation
from backend.schemas.evaluation import ClaimOut, EvaluationListItem, EvaluationOut

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/{evaluation_id}", response_model=EvaluationOut)
def get_history_item(
    evaluation_id: int,
    db: Session = Depends(get_db),
) -> EvaluationOut:
    """Return one full evaluation report by ID (no auth required)."""
    row = db.get(Evaluation, evaluation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    claims_out = [
        ClaimOut(
            id=i,
            text=cr.text,
            verdict=cr.verdict.value if hasattr(cr.verdict, "value") else str(cr.verdict).split(".")[-1].upper(),
            confidence=cr.confidence,
            rationale=cr.rationale,
            sources=cr.sources,
        )
        for i, cr in enumerate(row.claims)
    ]

    return EvaluationOut(
        id=row.id,
        question=row.question,
        ai_answer=row.ai_answer,
        trust_score=row.trust_score,
        ragas_faithfulness=row.ragas_faithfulness,
        ragas_context_precision=row.ragas_context_precision,
        corrected_answer=row.corrected_answer,
        follow_up_questions=row.follow_up_questions or [],
        created_at=row.created_at,
        claims=claims_out,
    )
