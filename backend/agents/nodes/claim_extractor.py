"""LangGraph node: extract atomic factual claims from an AI answer."""
from __future__ import annotations

from backend.agents.llm import claude_complete, extract_json
from backend.agents.state import PipelineState

_SYSTEM = (
    "You are a careful medical fact-checker. Your job is to split an AI-generated "
    "answer into the smallest possible atomic factual claims that can be independently "
    "verified against medical guidelines."
)

_PROMPT_TEMPLATE = """Given the user question and the AI-generated answer below, extract every atomic factual claim from the answer.

Rules:
- Each claim must be a single, self-contained statement that could be true or false on its own.
- Include numerical claims (dosages, percentages, durations) as separate claims.
- Do not include hedging, opinions, or generic safety disclaimers.
- Preserve the original wording as much as possible.
- Return ONLY a JSON array of strings. No prose, no markdown fences.

Question: {question}

AI answer:
\"\"\"
{answer}
\"\"\"

Return format: ["claim 1", "claim 2", ...]
"""


def extract_claims(state: PipelineState) -> PipelineState:
    """Populate ``state['claims']`` with atomic claims parsed from the answer.

    If Claude returns malformed JSON we fall back to treating the entire
    answer as a single claim so the pipeline can still produce a report.
    """
    prompt = _PROMPT_TEMPLATE.format(
        question=state["question"], answer=state["ai_answer"]
    )
    response = claude_complete(prompt, system=_SYSTEM, max_tokens=1024)
    try:
        parsed = extract_json(response)
    except ValueError:
        parsed = [state["ai_answer"]]

    if not isinstance(parsed, list):
        parsed = [str(parsed)]

    claims = [str(c).strip() for c in parsed if str(c).strip()]
    if not claims:
        claims = [state["ai_answer"]]

    return {"claims": claims}
