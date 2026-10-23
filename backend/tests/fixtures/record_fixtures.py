"""Regenerate ``llm_calls.jsonl``: ``python -m backend.tests.fixtures.record_fixtures``.

IMPORTANT: these fixtures are *canned* responses, written by hand to cover the
shapes real models produce (fenced JSON, prose around JSON, malformed output,
missing fields). They are keyed by the real request hash, so tests exercise the
true ``claude_complete`` -> cache path, but they are NOT recordings of a live
model. Real recordings live in backend/eval/cache/calls.jsonl.
"""
from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

OUT = Path(__file__).parent / "llm_calls.jsonl"

PASSAGE: Any = {
    "doc": "NICE-NG28-Type2-Diabetes",
    "page": 29,
    "chunk": 0,
    "score": 0.71,
    "text": (
        "1.13.1 For adults with type 2 diabetes and no relevant comorbidity, offer: "
        "modified-release metformin, and an SGLT-2 inhibitor."
    ),
    "source_url": "",
    "web_url": "https://www.nice.org.uk/guidance/ng28",
}

QUESTION = "What is the first-line drug for type 2 diabetes?"
ANSWER = "Metformin is first-line. Insulin is mandatory within 6 months of diagnosis."
CLAIM_1 = "Metformin is first-line for type 2 diabetes."
CLAIM_2 = "Insulin is mandatory within 6 months of diagnosis."

# Responses are consumed in call order by the scenario functions below.
SCENARIOS: list[tuple[str, list[str]]] = [
    (
        "pipeline",
        [
            '```json\n["' + CLAIM_1 + '", "' + CLAIM_2 + '"]\n```',
            '{"verdict": "SUPPORTED", "confidence": 0.9, "rationale": "NG28 1.13.1 offers metformin.", '
            '"passage": 1, "quote": "offer: modified-release metformin"}',
            'Here is my answer: {"verdict": "unsupported", "confidence": 0.2, "rationale": "Not addressed."}',
            "Metformin is offered, together with an SGLT-2 inhibitor. Sources: NICE NG28 p.29.",
            '["Is an SGLT-2 inhibitor also needed?", "When is insulin used?", "What are the HbA1c targets?"]',
        ],
    ),
    ("extract_malformed", ["Sorry, I cannot help with that."]),
    ("score_garbage", ["I believe the claim is fine."]),
]


def record() -> None:
    from backend.agents import call_cache, llm
    from backend.agents.state import PipelineState

    # Same provider/model resolution as the test environment (see backend/tests/conftest.py).
    os.environ['GROQ_API_KEY'] = 'test-key-not-real'
    os.environ['GROQ_MODEL'] = 'test-model'
    os.environ['ANTHROPIC_API_KEY'] = ''
    os.environ['SOURCEMD_CALL_CACHE'] = 'record'
    os.environ["SOURCEMD_CALL_CACHE_FILE"] = str(OUT)
    OUT.unlink(missing_ok=True)
    call_cache.reset_cache_state()

    queue: list[str] = []

    def fake_raw(provider, model, sys_msg, prompt, max_tokens, temperature):  # noqa: ANN001
        return queue.pop(0)

    llm._raw_complete = fake_raw

    def fake_retrieve(state: PipelineState) -> PipelineState:
        return {"retrieved": {c: [PASSAGE] for c in state.get("claims", [])}}


    from backend.agents.nodes.claim_extractor import extract_claims
    from backend.agents.nodes.scorer import score_claim, score_claims

    scenario_fns: dict[str, Callable[[], Any]] = {
        "pipeline": lambda: _pipeline(extract_claims, score_claims, fake_retrieve),
        "extract_malformed": lambda: extract_claims({"question": QUESTION, "ai_answer": "foo bar baz"}),
        "score_garbage": lambda: score_claim("Some claim.", [PASSAGE]),
    }
    for name, responses in SCENARIOS:
        queue[:] = responses
        scenario_fns[name]()
        assert not queue, f"scenario {name} did not consume all canned responses"
    print(f"Wrote {OUT}")


def _pipeline(extract_claims, score_claims, fake_retrieve) -> None:  # noqa: ANN001
    state: dict = {"question": QUESTION, "ai_answer": ANSWER}
    state.update(extract_claims(state))
    state.update(fake_retrieve(state))
    score_claims(state)


if __name__ == "__main__":
    record()


