"""Public /evaluate endpoint that runs the trust pipeline."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.agents.graph import run_pipeline
from backend.agents.ragas_eval import evaluate_with_ragas
from backend.auth.deps import get_current_user_optional
from backend.db.base import get_db
from backend.db.models import Claim, Evaluation, User, Verdict
from backend.schemas.evaluation import EvaluateRequest, EvaluationOut

router = APIRouter(tags=["evaluate"])


@router.post("/evaluate", response_model=EvaluationOut)
def evaluate(
    payload: EvaluateRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> EvaluationOut:
    """Run the full trust pipeline on a (question, ai_answer) pair.

    The endpoint is public; if a valid JWT is supplied, the resulting
    evaluation row is linked to that user so it shows up in /history.
    """
    try:
        result = run_pipeline(payload.question, payload.ai_answer)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    scored = result.get("scored_claims", [])
    ragas_scores = evaluate_with_ragas(payload.question, payload.ai_answer, scored)

    evaluation = Evaluation(
        user_id=user.id if user else None,
        question=payload.question,
        ai_answer=payload.ai_answer,
        trust_score=float(result.get("trust_score", 0.0)),
        ragas_faithfulness=ragas_scores.get("faithfulness"),
        ragas_context_precision=ragas_scores.get("context_precision"),
        corrected_answer=result.get("corrected_answer", ""),
        follow_up_questions=result.get("follow_up_questions", []),
    )
    db.add(evaluation)
    db.flush()  # populate evaluation.id for FK linkage

    for sc in scored:
        try:
            verdict = Verdict(sc["verdict"])
        except ValueError:
            verdict = Verdict.UNSUPPORTED
        db.add(
            Claim(
                evaluation_id=evaluation.id,
                text=sc["text"],
                verdict=verdict,
                confidence=float(sc.get("confidence", 0.0)),
                rationale=sc.get("rationale", ""),
                sources=sc.get("sources", []),
            )
        )

    db.commit()
    db.refresh(evaluation)
    return evaluation  # type: ignore[return-value]
