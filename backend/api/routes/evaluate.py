"""Public /evaluate endpoint — runs the trust pipeline and persists results."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.agents.graph import run_pipeline
from backend.agents.ragas_eval import evaluate_with_ragas
from backend.db.base import get_db
from backend.db.models import Claim, Evaluation
from backend.schemas.evaluation import ClaimOut, EvaluateRequest, EvaluationOut

router = APIRouter(tags=["evaluate"])


@router.post("/evaluate", response_model=EvaluationOut)
def evaluate(
    payload: EvaluateRequest,
    db: Session = Depends(get_db),
) -> EvaluationOut:
    """Run the full trust pipeline on a (question, ai_answer) pair.

    Results are persisted anonymously (no user account required) and returned
    to the caller. The numeric evaluation ID can be used to retrieve the report
    later via GET /history/{id}.
    """
    try:
        result = run_pipeline(payload.question, payload.ai_answer)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    scored = result.get("scored_claims", [])
    ragas_scores = evaluate_with_ragas(payload.question, payload.ai_answer, scored)

    eval_row = Evaluation(
        user_id=None,
        question=payload.question,
        ai_answer=payload.ai_answer,
        trust_score=float(result.get("trust_score", 0.0)),
        ragas_faithfulness=ragas_scores.get("faithfulness"),
        ragas_context_precision=ragas_scores.get("context_precision"),
        corrected_answer=result.get("corrected_answer", ""),
        follow_up_questions=result.get("follow_up_questions", []),
    )
    db.add(eval_row)
    db.flush()  # get the auto-generated id before adding claims

    claim_rows: list[Claim] = []
    for i, sc in enumerate(scored):
        claim_rows.append(
            Claim(
                evaluation_id=eval_row.id,
                text=sc["text"],
                verdict=str(sc.get("verdict", "UNSUPPORTED")).upper(),
                confidence=float(sc.get("confidence", 0.0)),
                rationale=sc.get("rationale", ""),
                sources=sc.get("sources", []),
            )
        )
    db.add_all(claim_rows)
    db.commit()
    db.refresh(eval_row)

    claims_out = [
        ClaimOut(
            id=i,
            text=cr.text,
            verdict=str(cr.verdict).upper(),
            confidence=cr.confidence,
            rationale=cr.rationale,
            sources=cr.sources,
        )
        for i, cr in enumerate(eval_row.claims)
    ]

    return EvaluationOut(
        id=eval_row.id,
        question=eval_row.question,
        ai_answer=eval_row.ai_answer,
        trust_score=eval_row.trust_score,
        ragas_faithfulness=eval_row.ragas_faithfulness,
        ragas_context_precision=eval_row.ragas_context_precision,
        corrected_answer=eval_row.corrected_answer,
        follow_up_questions=eval_row.follow_up_questions or [],
        created_at=eval_row.created_at,
        claims=claims_out,
    )
