"""Mechanical checks on the labelled dataset: ``python -m backend.eval.validate``.

- schema: labels, splits, ids, evidence present exactly where required
- evidence: every gold quote literally appears on the stated page of the cached PDF
- balance: label and split counts (printed, not enforced)

A passing run says the *evidence is transcribed correctly*. It does not say the
labels are right; that needs the label review in ``backend.eval.review``.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from backend.eval.corpus import load_pages
from backend.eval.schema import DEFAULT_DATASET, GoldAnswer, load_answers, schema_errors
from backend.eval.textnorm import quote_in


def evidence_errors(answers: list[GoldAnswer], pages: dict[str, list[tuple[int, str]]]) -> list[str]:
    """Return one message per gold quote that is not found on its stated page."""
    by_doc = {doc: dict(p) for doc, p in pages.items()}
    errors: list[str] = []
    for a in answers:
        for c in a.claims:
            ev = c.evidence
            if ev is None:
                continue
            page_text = by_doc.get(ev.doc, {}).get(ev.page)
            if page_text is None:
                errors.append(f"{c.id}: no page {ev.page} in {ev.doc}")
            elif not quote_in(ev.quote, page_text):
                errors.append(f"{c.id}: quote not found on {ev.doc} p.{ev.page}: {ev.quote[:80]!r}")
    return errors


def summary(answers: list[GoldAnswer]) -> str:
    """Human-readable label/split/topic counts."""
    lines = []
    for split in ("dev", "test"):
        subset = [a for a in answers if a.split == split]
        counts = Counter(c.label for a in subset for c in a.claims)
        lines.append(
            f"{split}: {len(subset)} answers, {sum(counts.values())} claims {dict(counts)}, "
            f"reliable answers {sum(a.reliable for a in subset)}"
        )
    lines.append(f"reviewed answers: {sum(a.reviewed for a in answers)}/{len(answers)}")
    topics = Counter(a.topic for a in answers)
    lines.append(f"topics: {dict(topics)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    args = ap.parse_args(argv)

    answers = load_answers(args.dataset)
    errors = schema_errors(answers) + evidence_errors(answers, load_pages())
    print(summary(answers))
    if errors:
        print(f"\n{len(errors)} problem(s):", file=sys.stderr)
        for e in errors:
            print("  " + e, file=sys.stderr)
        return 1
    print("\nOK: schema valid and every gold quote found on its page.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
