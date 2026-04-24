"""LangGraph node: score each claim and synthesize a corrected answer."""
from __future__ import annotations

from backend.agents.llm import claude_complete, extract_json
from backend.agents.state import PipelineState, RetrievedPassage, ScoredClaim

_VERDICTS = {"SUPPORTED", "UNSUPPORTED", "CONTRADICTED"}

_SCORE_WEIGHTS = {
    "SUPPORTED": 1.0,
    "UNSUPPORTED": 0.3,
    "CONTRADICTED": 0.0,
}

_SCORER_SYSTEM = (
    "You are a careful medical fact-checker. Given a claim and retrieved passages "
    "from authoritative guidelines, decide whether the claim is SUPPORTED, "
    "UNSUPPORTED, or CONTRADICTED by the evidence. Use only the provided passages."
)

_SCORER_PROMPT = """Claim: {claim}

Retrieved passages from medical guidelines:
{passages}

Task: classify the claim against the passages and return STRICT JSON:
{{
  "verdict": "SUPPORTED" | "UNSUPPORTED" | "CONTRADICTED",
  "confidence": number between 0 and 1,
  "rationale": "one or two sentences citing the passage(s) that drove the decision"
}}

Rules:
- "SUPPORTED" = passages clearly affirm the claim.
- "CONTRADICTED" = passages clearly state the opposite.
- "UNSUPPORTED" = passages are silent or only tangentially related.
- Confidence should reflect how strong the evidence is, not how plausible the claim sounds.
- Return ONLY the JSON object.
"""

_CORRECTION_SYSTEM = (
    "You are a careful medical writer. Rewrite an AI-generated answer using the "
    "retrieved guideline passages provided. Apply these rules strictly:\n"
    "- SUPPORTED claims: keep them, they are evidence-backed.\n"
    "- CONTRADICTED claims: correct or remove them — the evidence actively disagrees.\n"
    "- UNSUPPORTED claims: the retrieved sources simply did not cover this topic. "
    "Do NOT say the claim is wrong or should not be considered. Instead, omit it or "
    "note it was not addressed in the retrieved sources.\n"
    "Do not introduce new facts not present in the passages."
)

_CORRECTION_PROMPT = """Original question: {question}

Original AI answer:
\"\"\"
{answer}
\"\"\"

Claim-by-claim evidence:
{evidence}

Write a revised answer to the question that:
- Keeps and reinforces SUPPORTED claims with evidence.
- Clearly corrects CONTRADICTED claims using the passage evidence.
- For UNSUPPORTED claims: omit them silently OR add a brief note like
  "(not addressed in retrieved sources)" — never say they are incorrect.
- Keeps the tone clinical and concise (under 200 words).
- Ends with a short "Sources:" line listing document names and page numbers used.

Return only the rewritten answer as plain text."""

_FOLLOWUP_SYSTEM = (
    "You are a medical education assistant. Generate concise, clinically relevant "
    "follow-up questions that deepen understanding of the topic."
)

_FOLLOWUP_PROMPT = """A user asked this medical question and received a trust-scored answer.

Original question: {question}
Trust score: {trust_score:.0f}/100
Unsupported/Contradicted claims: {bad_claims}

Generate exactly 3 follow-up questions a curious user might ask next to better understand
this topic or verify the evidence. Make them specific and clinically useful.

Return ONLY a JSON array of 3 question strings. Example:
["Question 1?", "Question 2?", "Question 3?"]"""


def _format_passages(passages: list[RetrievedPassage]) -> str:
    """Format retrieved passages into a numbered block for the scorer prompt."""
    if not passages:
        return "(no passages retrieved)"
    lines: list[str] = []
    for i, p in enumerate(passages, start=1):
        lines.append(
            f"[{i}] {p['doc']} p.{p['page']} (similarity={p['score']:.2f}):\n{p['text']}"
        )
    return "\n\n".join(lines)


def _format_evidence(scored: list[ScoredClaim]) -> str:
    """Format the scored claim list for the correction prompt."""
    lines: list[str] = []
    for i, sc in enumerate(scored, start=1):
        source_tags = ", ".join(
            f"{s['doc']} p.{s['page']}" for s in sc["sources"]
        ) or "(none)"
        lines.append(
            f"{i}. Claim: {sc['text']}\n"
            f"   Verdict: {sc['verdict']} (conf={sc['confidence']:.2f})\n"
            f"   Rationale: {sc['rationale']}\n"
            f"   Sources: {source_tags}"
        )
    return "\n".join(lines)


def _aggregate_trust_score(scored: list[ScoredClaim]) -> float:
    """Compute the 0-100 aggregate trust score from per-claim verdicts.

    Each claim contributes a fixed amount based on its verdict:
    - SUPPORTED:    uses confidence directly (0.0–1.0), rewarding high-confidence support
    - UNSUPPORTED:  fixed 0.3 — always penalises the score regardless of confidence,
                    preventing 0%-confident UNSUPPORTED claims from being silently ignored
    - CONTRADICTED: fixed 0.0 — maximum penalty

    Using a simple mean (not confidence-weighted) ensures every claim counts equally
    and that UNSUPPORTED claims cannot inflate the score by having zero confidence.
    """
    if not scored:
        return 0.0
    total = 0.0
    for sc in scored:
        verdict = sc.get("verdict", "UNSUPPORTED")
        c = max(0.0, min(1.0, float(sc.get("confidence", 0.0))))
        if verdict == "SUPPORTED":
            total += c
        elif verdict == "UNSUPPORTED":
            total += 0.3          # fixed floor — always a penalty
        else:                      # CONTRADICTED
            total += 0.0
    return round((total / len(scored)) * 100.0, 2)


def score_claims(state: PipelineState) -> PipelineState:
    """Score each claim and synthesize a corrected answer.

    Produces ``scored_claims``, ``trust_score`` (0-100), and
    ``corrected_answer`` in the updated state.
    """
    claims = state.get("claims", [])
    retrieved = state.get("retrieved", {})
    scored: list[ScoredClaim] = []

    for claim in claims:
        passages = retrieved.get(claim, [])
        prompt = _SCORER_PROMPT.format(
            claim=claim, passages=_format_passages(passages)
        )
        response = claude_complete(
            prompt, system=_SCORER_SYSTEM, max_tokens=512, temperature=0.0
        )
        try:
            data = extract_json(response)
        except ValueError:
            data = {}

        if not isinstance(data, dict):
            data = {}

        verdict = str(data.get("verdict", "UNSUPPORTED")).upper()
        if verdict not in _VERDICTS:
            verdict = "UNSUPPORTED"
        try:
            confidence = float(data.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))
        rationale = str(data.get("rationale", "")).strip()

        scored.append(
            ScoredClaim(
                text=claim,
                verdict=verdict,
                confidence=round(confidence, 4),
                rationale=rationale,
                sources=passages,
            )
        )

    trust_score = _aggregate_trust_score(scored)

    corrected_prompt = _CORRECTION_PROMPT.format(
        question=state["question"],
        answer=state["ai_answer"],
        evidence=_format_evidence(scored),
    )
    corrected_answer = claude_complete(
        corrected_prompt,
        system=_CORRECTION_SYSTEM,
        max_tokens=800,
        temperature=0.0,
    )

    # Generate follow-up question suggestions.
    bad_claims = [
        sc["text"] for sc in scored if sc["verdict"] in ("UNSUPPORTED", "CONTRADICTED")
    ]
    followup_prompt = _FOLLOWUP_PROMPT.format(
        question=state["question"],
        trust_score=trust_score,
        bad_claims="; ".join(bad_claims) if bad_claims else "none",
    )
    try:
        followup_raw = claude_complete(
            followup_prompt, system=_FOLLOWUP_SYSTEM, max_tokens=256, temperature=0.3
        )
        followups = extract_json(followup_raw)
        if not isinstance(followups, list):
            followups = []
        follow_up_questions = [str(q).strip() for q in followups[:3] if str(q).strip()]
    except Exception:  # noqa: BLE001
        follow_up_questions = []

    return {
        "scored_claims": scored,
        "trust_score": trust_score,
        "corrected_answer": corrected_answer,
        "follow_up_questions": follow_up_questions,
    }
