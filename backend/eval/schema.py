"""Dataset schema and loader for the labelled claim-verification set."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

LABELS = ("SUPPORTED", "UNSUPPORTED", "CONTRADICTED")
SPLITS = ("dev", "test")
ORIGINS = ("verbatim", "paraphrase", "perturbed", "out_of_corpus")

DATA_DIR = Path(__file__).parent / "data"
DEFAULT_DATASET = DATA_DIR / "answers.jsonl"


@dataclass(frozen=True)
class Evidence:
    """Gold evidence: a quote that must appear on ``page`` of ``doc``."""

    doc: str
    page: int
    quote: str


@dataclass(frozen=True)
class GoldClaim:
    """One labelled atomic claim."""

    id: str
    text: str
    label: str
    origin: str
    evidence: Evidence | None
    note: str = ""


@dataclass(frozen=True)
class GoldAnswer:
    """A short AI-style answer and its labelled claims (the unit of splitting)."""

    id: str
    split: str
    topic: str
    question: str
    ai_answer: str
    claims: list[GoldClaim]
    reviewed: bool = False
    reviewed_by: str = ""
    meta: dict[str, str] = field(default_factory=dict)

    @property
    def reliable(self) -> bool:
        """Gold answer-level label: every claim is SUPPORTED."""
        return all(c.label == "SUPPORTED" for c in self.claims)


def _parse_claim(raw: dict) -> GoldClaim:
    ev = raw.get("evidence")
    evidence = Evidence(ev["doc"], int(ev["page"]), ev["quote"]) if ev else None
    return GoldClaim(
        id=raw["id"],
        text=raw["text"],
        label=raw["label"],
        origin=raw["origin"],
        evidence=evidence,
        note=raw.get("note", ""),
    )


def _parse_answer(raw: dict) -> GoldAnswer:
    return GoldAnswer(
        id=raw["id"],
        split=raw["split"],
        topic=raw["topic"],
        question=raw["question"],
        ai_answer=raw["ai_answer"],
        claims=[_parse_claim(c) for c in raw["claims"]],
        reviewed=bool(raw.get("reviewed", False)),
        reviewed_by=raw.get("reviewed_by", ""),
    )


def load_answers(path: Path = DEFAULT_DATASET) -> list[GoldAnswer]:
    """Load every answer from a JSONL file (one JSON object per line)."""
    answers: list[GoldAnswer] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("//"):
                answers.append(_parse_answer(json.loads(line)))
    return answers


def schema_errors(answers: list[GoldAnswer]) -> list[str]:
    """Return structural problems (bad labels, splits, duplicate ids, missing evidence)."""
    errors: list[str] = []
    seen_answers: set[str] = set()
    seen_claims: set[str] = set()
    for a in answers:
        if a.id in seen_answers:
            errors.append(f"duplicate answer id {a.id}")
        seen_answers.add(a.id)
        if a.split not in SPLITS:
            errors.append(f"{a.id}: bad split {a.split!r}")
        if not a.claims:
            errors.append(f"{a.id}: no claims")
        for c in a.claims:
            if c.id in seen_claims:
                errors.append(f"duplicate claim id {c.id}")
            seen_claims.add(c.id)
            if c.label not in LABELS:
                errors.append(f"{c.id}: bad label {c.label!r}")
            if c.origin not in ORIGINS:
                errors.append(f"{c.id}: bad origin {c.origin!r}")
            if c.label in ("SUPPORTED", "CONTRADICTED") and c.evidence is None:
                errors.append(f"{c.id}: {c.label} claim needs gold evidence")
            if c.label == "UNSUPPORTED" and c.evidence is not None:
                errors.append(f"{c.id}: UNSUPPORTED claim must not carry evidence")
    return errors
