"""POST /follow-up — answer a follow-up question using context sent by the client."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.agents.llm import claude_complete

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


class ClaimContext(BaseModel):
    """Minimal claim info sent by the client for follow-up context."""

    verdict: str
    text: str


class FollowUpRequest(BaseModel):
    """Request body for POST /follow-up.

    The client sends the evaluation context so nothing needs to be stored
    server-side between requests.
    """

    question: str = Field(min_length=3, max_length=2000)
    original_question: str = Field(min_length=3, max_length=4000)
    ai_answer: str = Field(min_length=1, max_length=10000)
    corrected_answer: str = Field(min_length=1, max_length=10000)
    claims: list[ClaimContext] = []


class FollowUpResponse(BaseModel):
    """Response from POST /follow-up."""

    answer: str


@router.post("/follow-up", response_model=FollowUpResponse)
def follow_up(payload: FollowUpRequest) -> FollowUpResponse:
    """Answer a follow-up question grounded in the client-supplied evaluation context.

    No database lookup is performed — the caller provides all context needed.
    """
    claim_lines = [f"  - [{c.verdict}] {c.text}" for c in payload.claims]
    claim_summary = "\n".join(claim_lines) if claim_lines else "  (no claims)"

    prompt = _PROMPT_TEMPLATE.format(
        question=payload.original_question,
        ai_answer=payload.ai_answer,
        corrected_answer=payload.corrected_answer,
        claim_summary=claim_summary,
        follow_up=payload.question,
    )

    try:
        answer = claude_complete(prompt, system=_SYSTEM, max_tokens=512, temperature=0.3)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return FollowUpResponse(answer=answer)
