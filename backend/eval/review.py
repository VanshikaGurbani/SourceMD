"""Interactive label review: ``python -m backend.eval.review --reviewer "Your Name"``.

Walks every unreviewed answer, shows each claim with its draft label and gold
evidence (for UNSUPPORTED claims: the closest corpus passages, so you can
confirm the corpus really is silent), and lets you accept or change the label.
Accepting an answer stamps ``reviewed: true`` and your name. Only reviewed
answers are scored by ``backend.eval.run`` (unless --include-unreviewed).

Keys per claim: Enter = agree, s/u/c = relabel SUPPORTED/UNSUPPORTED/CONTRADICTED,
x = flag claim as ambiguous (the whole answer is then left unreviewed), q = save and quit.
Progress is saved after every answer, so you can stop and resume any time.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.eval.schema import DEFAULT_DATASET

_KEYS = {"s": "SUPPORTED", "u": "UNSUPPORTED", "c": "CONTRADICTED"}


def _closest_passages(claim: str, k: int = 3) -> list[str]:
    """Top-k BM25 corpus chunks for ``claim`` formatted for display."""
    from backend.eval.corpus import CorpusIndex
    from backend.eval.retrieval import EvalRetriever

    retriever = _closest_passages.__dict__.setdefault("r", EvalRetriever(CorpusIndex.load()))
    return [
        f"[{p['doc']} p.{p['page']}] {p['text'][:300].replace(chr(10), ' ')}"
        for p in retriever.retrieve(claim, "bm25")[:k]
    ]


def _save(rows: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    ap.add_argument("--reviewer", required=True, help="your name, stored as reviewed_by")
    ap.add_argument("--split", choices=["dev", "test", "all"], default="all")
    args = ap.parse_args(argv)

    rows = [json.loads(line) for line in args.dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    todo = [r for r in rows if not r["reviewed"] and args.split in ("all", r["split"])]
    print(f"{len(todo)} unreviewed answers to go.\n")

    for r in todo:
        print("=" * 78)
        print(f"{r['id']} [{r['split']}] {r['topic']}\nQ: {r['question']}\nAnswer: {r['ai_answer']}\n")
        clean = True
        for c in r["claims"]:
            print(f"- {c['id']}: {c['text']}")
            print(f"  draft label: {c['label']}   ({c['origin']}; {c['note']})")
            ev = c["evidence"]
            if ev:
                print(f"  gold evidence [{ev['doc']} p.{ev['page']}]: \"{ev['quote']}\"")
            else:
                print("  closest corpus passages (is the corpus really silent?):")
                for line in _closest_passages(c["text"]):
                    print("    " + line)
            while True:
                key = input("  [Enter]=agree  s/u/c=relabel  x=ambiguous  q=quit > ").strip().lower()
                if key == "":
                    break
                if key in _KEYS:
                    c["label"] = _KEYS[key]
                    if c["label"] == "UNSUPPORTED":
                        c["evidence"] = None
                    elif c["evidence"] is None:
                        print("  A SUPPORTED/CONTRADICTED claim needs evidence; edit answers.jsonl by hand.")
                        clean = False
                    break
                if key == "x":
                    clean = False
                    break
                if key == "q":
                    _save(rows, args.dataset)
                    print("Saved.")
                    return 0
        if clean:
            r["reviewed"], r["reviewed_by"] = True, args.reviewer
        else:
            print("  Answer left unreviewed (ambiguous or needs edits).")
        _save(rows, args.dataset)

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
