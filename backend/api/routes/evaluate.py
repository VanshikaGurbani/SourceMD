"""Public /evaluate endpoint — runs the trust pipeline, returns results directly.

No data is saved to the database. All persistence is handled client-side.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from backend.agents.graph import run_pipeline
from backend.agents.ragas_eval import evaluate_with_ragas
from backend.schemas.evaluation import ClaimOut, EvaluateRequest, EvaluationOut

router = APIRouter(tags=["evaluate"])


@router.post("/evaluate", response_model=EvaluationOut)
def evaluate(payload: EvaluateRequest) -> EvaluationOut:
    """Run the full trust pipeline on a (question, ai_answer) pair.

    Results are returned directly to the caller and never stored server-side.
    The client is responsible for persisting the evaluation locally.
    """
    try:
        result = run_pipeline(payload.question, payload.ai_answer)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    scored = result.get("scored_claims", [])
    ragas_scores = evaluate_with_ragas(payload.question, payload.ai_answer, scored)

    claims = [
        ClaimOut(
            id=i,
            text=sc["text"],
            verdict=str(sc.get("verdict", "UNSUPPORTED")).upper(),
            confidence=float(sc.get("confidence", 0.0)),
            rationale=sc.get("rationale", ""),
            sources=sc.get("sources", []),
        )
        for i, sc in enumerate(scored)
    ]

    return EvaluationOut(
        id=str(uuid.uuid4()),
        question=payload.question,
        ai_answer=payload.ai_answer,
        trust_score=float(result.get("trust_score", 0.0)),
        ragas_faithfulness=ragas_scores.get("faithfulness"),
        ragas_context_precision=ragas_scores.get("context_precision"),
        corrected_answer=result.get("corrected_answer", ""),
        follow_up_questions=result.get("follow_up_questions", []),
        created_at=datetime.now(timezone.utc),
        claims=claims,
    )
