"""POST /follow-up — answer a follow-up question using evaluation context."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.agents.llm import claude_complete
from backend.db.base import get_db
from backend.db.models import Evaluation

router = APIRouter(tags=["followup"])

_SYSTEM = (
    "You are a careful medical assistant. Answer the follow-up question using only "
    "the information from the original evaluation context provided. Be concise and "
    "cite the guideline source where relevant."
)

_PROMPT_TEMPLATE = """A user previously evaluated an AI medical answer using SourceMD.

Original question: {question}

Original AI answer:
\"\"\"{ai_answer}\"\"\"

Corrected, source-backed answer:
\"\"\"{corrected_answer}\"\"\"

Claim verdicts:
{claim_summary}

Now the user has a follow-up question:
\"{follow_up}\"

Answer the follow-up question clearly and concisely (2-4 sentences).
Base your answer on the corrected answer and claim verdicts above.
If the context doesn't contain enough information to answer, say so explicitly."""


class FollowUpRequest(BaseModel):
    """Request body for POST /follow-up."""

    evaluation_id: int
    question: str = Field(min_length=3, max_length=2000)


class FollowUpResponse(BaseModel):
    """Response from POST /follow-up."""

    answer: str
    evaluation_id: int


@router.post("/follow-up", response_model=FollowUpResponse)
def follow_up(
    payload: FollowUpRequest,
    db: Session = Depends(get_db),
) -> FollowUpResponse:
    """Answer a follow-up question grounded in a previous evaluation's context.

    Retrieves the evaluation by id, builds a context-rich prompt, and returns
    a Claude / Groq response. The endpoint is intentionally public so users
    can ask follow-ups without being logged in.
    """
    evaluation = db.get(Evaluation, payload.evaluation_id)
    if evaluation is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    claim_lines = []
    for c in evaluation.claims:
        claim_lines.append(f"  - [{c.verdict}] {c.text}")
    claim_summary = "\n".join(claim_lines) if claim_lines else "  (no claims)"

    prompt = _PROMPT_TEMPLATE.format(
        question=evaluation.question,
        ai_answer=evaluation.ai_answer,
        corrected_answer=evaluation.corrected_answer,
        claim_summary=claim_summary,
        follow_up=payload.question,
    )

    try:
        answer = claude_complete(prompt, system=_SYSTEM, max_tokens=512, temperature=0.3)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return FollowUpResponse(answer=answer, evaluation_id=payload.evaluation_id)
