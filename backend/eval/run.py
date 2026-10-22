"""One-command evaluation: ``python -m backend.eval.run``.

Scores every labelled claim under several (retrieval, LLM) configurations and
regenerates ``docs/EVAL_RESULTS.md``.

Safety defaults:
- Without ``--allow-api`` the runner only *replays* recorded calls
  (SOURCEMD_CALL_CACHE=replay). It never spends API credits.
- ``--dry-run`` prints how many uncached LLM/Tavily calls each config needs.
- Only claims from answers with ``reviewed: true`` are scored, unless
  ``--include-unreviewed`` is passed, in which case the report is stamped PROVISIONAL.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from backend.agents import call_cache
from backend.agents.citations import verify_citation
from backend.agents.nodes.scorer import _aggregate_trust_score, score_claim
from backend.agents.quality_metrics import compute_quality_metrics
from backend.agents.state import RetrievedPassage, ScoredClaim
from backend.eval import metrics as M
from backend.eval.schema import (
    DEFAULT_DATASET,
    LABELS,
    GoldAnswer,
    GoldClaim,
    load_answers,
    schema_errors,
)
from backend.eval.textnorm import token_coverage

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT = REPO_ROOT / "docs" / "EVAL_RESULTS.md"
HIT_COVERAGE = 0.5  # a chunk "hits" if it contains >= 50% of the gold quote's tokens


@dataclass(frozen=True)
class Config:
    """One ablation: which retrieval mode and which LLM provider."""

    name: str
    retrieval: str
    provider: str
    description: str


CONFIGS: dict[str, Config] = {
    c.name: c
    for c in [
        Config("llm_only_groq", "none", "groq", "No retrieval; Llama 3.3 70B judges from its own knowledge"),
        Config("corpus_groq", "dense", "groq", "Dense top-3 over NICE/AHA corpus; Llama 3.3 70B"),
        Config("corpus_web_groq", "dense_web", "groq", "Corpus + Tavily when similarity < 0.35 (production); Llama 3.3 70B"),
        Config("corpus_claude", "dense", "anthropic", "Dense top-3 over corpus; Claude"),
        Config("bm25_groq", "bm25", "groq", "BM25 top-3; Llama 3.3 70B"),
        Config("hybrid_groq", "hybrid", "groq", "Hybrid BM25+dense (RRF) top-3; Llama 3.3 70B"),
    ]
}
DEFAULT_CONFIGS = ["llm_only_groq", "corpus_groq", "corpus_web_groq", "corpus_claude"]
RETRIEVAL_REPORTED = ["dense", "bm25", "hybrid"]


@dataclass
class ClaimResult:
    """Outcome for one gold claim under one config."""

    gold: GoldClaim
    answer_id: str
    scored: ScoredClaim

    @property
    def pred(self) -> str:
        return self.scored["verdict"]

    def citation_literal(self) -> bool:
        """The cited quote literally appears in the passage it cites."""
        return verify_citation(
            self.scored.get("quote", ""),
            self.scored.get("cited_passage"),
            self.scored["sources"],
        )

    def citation_valid(self) -> bool:
        """Literal quote AND the cited passage covers the gold evidence."""
        if not self.citation_literal() or self.gold.evidence is None:
            return False
        idx = self.scored.get("cited_passage")
        assert idx is not None
        passage = self.scored["sources"][idx - 1]
        return (
            passage["doc"] == self.gold.evidence.doc
            and token_coverage(self.gold.evidence.quote, passage["text"]) >= HIT_COVERAGE
        )


@dataclass
class ConfigRun:
    """All results (or the reason there are none) for one config."""

    config: Config
    results: list[ClaimResult] = field(default_factory=list)
    skipped_reason: str = ""


# --------------------------------------------------------------------------
# Running
# --------------------------------------------------------------------------

def retrieval_hit(claim: GoldClaim, passages: list[RetrievedPassage]) -> bool:
    """True if any retrieved chunk from the gold doc covers the gold quote."""
    ev = claim.evidence
    if ev is None:
        return False
    return any(
        p["doc"] == ev.doc and token_coverage(ev.quote, p["text"]) >= HIT_COVERAGE
        for p in passages
    )


def run_config(cfg: Config, answers: list[GoldAnswer], retriever) -> ConfigRun:
    """Score every claim of ``answers`` under ``cfg``."""
    run = ConfigRun(cfg)
    for ans in answers:
        for gc in ans.claims:
            passages = retriever.retrieve(gc.text, cfg.retrieval)
            scored = score_claim(
                gc.text,
                passages,
                provider=cfg.provider,
                use_retrieval_prompt=cfg.retrieval != "none",
            )
            run.results.append(ClaimResult(gc, ans.id, scored))
    return run


def trust_scores(run: ConfigRun, answers: list[GoldAnswer]) -> tuple[list[float], list[bool], list[float]]:
    """Per-answer (trust_score, gold_reliable, gold_fraction_supported)."""
    by_answer: dict[str, list[ClaimResult]] = {}
    for r in run.results:
        by_answer.setdefault(r.answer_id, []).append(r)
    scores, reliable, frac = [], [], []
    for ans in answers:
        rs = by_answer.get(ans.id, [])
        if not rs:
            continue
        scores.append(_aggregate_trust_score([r.scored for r in rs]))
        reliable.append(ans.reliable)
        frac.append(sum(c.label == "SUPPORTED" for c in ans.claims) / len(ans.claims))
    return scores, reliable, frac


def summarize(run: ConfigRun, answers: list[GoldAnswer]) -> dict:
    """Compute every headline metric (with bootstrap CIs) for one config."""
    gold = [r.gold.label for r in run.results]
    pred = [r.pred for r in run.results]
    n = len(gold)
    g_arr = np.array(gold)
    p_arr = np.array(pred)

    def stat(fn):
        return lambda idx: fn(list(g_arr[idx]), list(p_arr[idx]))

    out: dict = {"n_claims": n}
    out["accuracy"] = M.accuracy(gold, pred)
    out["accuracy_ci"] = M.bootstrap_ci(n, stat(M.accuracy))
    out["macro_f1"] = M.macro_f1(gold, pred)
    out["macro_f1_ci"] = M.bootstrap_ci(n, stat(M.macro_f1))
    out["contra_recall"] = M.recall_for(gold, pred, "CONTRADICTED")
    out["contra_recall_ci"] = M.bootstrap_ci(n, stat(lambda g, p: M.recall_for(g, p, "CONTRADICTED")))
    out["confusion"] = M.confusion_matrix(gold, pred)
    out["per_class"] = M.per_class_prf(gold, pred)

    # Citation checks over claims the system committed to (SUPPORTED/CONTRADICTED).
    committed = [r for r in run.results if r.pred in ("SUPPORTED", "CONTRADICTED")]
    out["n_committed"] = len(committed)
    if run.config.retrieval == "none" or not committed:
        out["citation_literal"] = out["citation_valid"] = float("nan")
    else:
        out["citation_literal"] = sum(r.citation_literal() for r in committed) / len(committed)
        out["citation_valid"] = sum(r.citation_valid() for r in committed) / len(committed)
        flags = np.array([r.citation_valid() for r in committed], dtype=float)
        out["citation_valid_ci"] = M.bootstrap_ci(len(flags), lambda idx: float(flags[idx].mean()))

    # Model's own flagged-claim rate (what the app calls "hallucination rate").
    out["flagged_rate"] = compute_quality_metrics([r.scored for r in run.results])["hallucination_rate"]
    gold_flagged = sum(g != "SUPPORTED" for g in gold) / n if n else float("nan")
    out["gold_flagged_rate"] = gold_flagged

    # Trust score validity at answer level.
    scores, reliable, frac = trust_scores(run, answers)
    out["n_answers"] = len(scores)
    out["auroc"] = M.auroc(scores, reliable)
    s_arr, r_arr = np.array(scores), np.array(reliable)
    out["auroc_ci"] = M.bootstrap_ci(len(scores), lambda idx: M.auroc(s_arr[idx], r_arr[idx]))
    out["spearman"] = M.spearman(scores, frac)
    return out


def _mean_ci(values: np.ndarray) -> tuple[float, float]:
    """Bootstrap CI of the mean of a 0/1 array."""
    return M.bootstrap_ci(len(values), lambda idx: float(values[idx].mean()))


def retrieval_table(answers: list[GoldAnswer], retriever) -> dict[str, dict]:
    """Offline retrieval hit@3 per mode over claims that carry gold evidence."""
    claims = [c for a in answers for c in a.claims if c.evidence is not None]
    out: dict[str, dict] = {}
    for mode in RETRIEVAL_REPORTED:
        hits = np.array([retrieval_hit(c, retriever.retrieve(c.text, mode)) for c in claims], dtype=float)
        out[mode] = {
            "n": len(hits),
            "hit3": float(hits.mean()) if len(hits) else float("nan"),
            "ci": _mean_ci(hits),
        }
    return out


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def render_report(
    *,
    runs: list[ConfigRun],
    summaries: dict[str, dict],
    retr: dict[str, dict],
    answers: list[GoldAnswer],
    split: str,
    provisional: bool,
    models: dict[str, str],
) -> str:
    """Render the Markdown results document."""
    n_claims = sum(len(a.claims) for a in answers)
    label_counts = {lab: sum(c.label == lab for a in answers for c in a.claims) for lab in LABELS}
    lines: list[str] = ["# Evaluation results", ""]
    if provisional:
        lines += [
            "> **PROVISIONAL**: this run includes claims whose labels have not been confirmed by a human reviewer",
            "> (`reviewed: false`). Do not quote these numbers.",
            "",
        ]
    lines += [
        "_Generated by `python -m backend.eval.run`; do not edit by hand._",
        "",
        f"- Date: {dt.date.today().isoformat()}  |  commit: `{_git_sha()}`",
        f"- Split: **{split}**  |  {len(answers)} answers, {n_claims} claims "
        f"({', '.join(f'{k}: {v}' for k, v in label_counts.items())})",
        f"- Models: Groq `{models['groq']}`, Anthropic `{models['anthropic']}`",
        "- Labels are relative to the ingested corpus (NICE NG28/NG136/CG181, AHA 2025 CPR/ECC), not absolute medical truth.",
        "- Intervals are 95% percentile bootstrap CIs; with this few claims they are wide and overlapping intervals mean the configs are not distinguishable.",
        "",
        "## Claim verification",
        "",
        "| Config | Claims | Accuracy | Macro-F1 | CONTRADICTED recall | Citation: quote literal | Citation: valid | Trust AUROC |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for run in runs:
        name = run.config.name
        if run.skipped_reason:
            lines.append(f"| `{name}` | - | not run: {run.skipped_reason} | | | | | |")
            continue
        s = summaries[name]
        lit = "n/a" if np.isnan(s["citation_literal"]) else f"{s['citation_literal']:.2f}"
        val = "n/a" if np.isnan(s["citation_valid"]) else M.fmt_ci(s["citation_valid"], s["citation_valid_ci"])
        lines.append(
            f"| `{name}` | {s['n_claims']} | {M.fmt_ci(s['accuracy'], s['accuracy_ci'])} | "
            f"{M.fmt_ci(s['macro_f1'], s['macro_f1_ci'])} | {M.fmt_ci(s['contra_recall'], s['contra_recall_ci'])} | "
            f"{lit} | {val} | {M.fmt_ci(s['auroc'], s['auroc_ci'])} (n={s['n_answers']}) |"
        )
    lines += ["", "Config definitions:", ""]
    for run in runs:
        lines.append(f"- `{run.config.name}`: {run.config.description}")

    lines += ["", "## Retrieval (offline, no LLM)", "",
              "Share of claims with gold evidence for which at least one of the top-3 chunks (same document) "
              f"contains >= {int(HIT_COVERAGE * 100)}% of the gold quote's tokens.", "",
              "| Mode | Claims | hit@3 |", "|---|---|---|"]
    for mode, r in retr.items():
        lines.append(f"| {mode} | {r['n']} | {M.fmt_ci(r['hit3'], r['ci'])} |")

    lines += ["", "## Details per config", ""]
    for run in runs:
        if run.skipped_reason:
            continue
        s = summaries[run.config.name]
        lines += [f"### `{run.config.name}`", "", "Confusion matrix (rows = gold, columns = predicted):", "",
                  "| gold \\ pred | " + " | ".join(LABELS) + " |", "|---|---|---|---|"]
        for lab, row in zip(LABELS, s["confusion"], strict=True):
            lines.append(f"| {lab} | " + " | ".join(str(v) for v in row) + " |")
        lines += ["", "| Class | Precision | Recall | F1 | Support |", "|---|---|---|---|---|"]
        for lab in LABELS:
            c = s["per_class"][lab]
            lines.append(f"| {lab} | {c['precision']:.2f} | {c['recall']:.2f} | {c['f1']:.2f} | {int(c['support'])} |")
        fr = s["flagged_rate"]
        fr_txt = "n/a" if fr is None else f"{fr:.2f}"
        rho = s["spearman"]
        rho_txt = "n/a" if np.isnan(rho) else f"{rho:.2f}"
        lines += ["", f"- Trust score vs gold: AUROC {M.fmt_ci(s['auroc'], s['auroc_ci'])}, Spearman vs gold fraction-supported "
                  f"{rho_txt} ({s['n_answers']} answers).",
                  "- Flagged-claim rate (the app's former \"hallucination rate\": share of the model's own "
                  f"UNSUPPORTED/CONTRADICTED verdicts): {fr_txt} vs gold share of non-SUPPORTED claims "
                  f"{s['gold_flagged_rate']:.2f}. This is not an accuracy measure.", ""]

    lines += ["## Limitations", "",
              "- Small dataset (~100 claims, test split ~40%): intervals above are wide; differences of a few points are noise.",
              "- Labels are corpus-relative. `llm_only_*` is judged against corpus labels, so true-but-not-in-corpus claims count as errors when the model calls them SUPPORTED. `corpus_web_*` can likewise be 'wrong' for claims the web legitimately supports.",
              "- Claims were drafted from the corpus text (supported = verbatim/paraphrased guideline sentence, contradicted = minimally edited sentence, unsupported = on-topic claim the corpus does not address) and then confirmed by a human reviewer; style is cleaner than real LLM output, so absolute accuracy is likely optimistic.",
              "- Claim extraction is not evaluated here (gold claims are fed in).",
              "- Trust AUROC is answer-level over a few dozen answers; treat as indicative only.",
              "- LLM outputs are replayed from `backend/eval/cache/calls.jsonl`; a different model version or prompt requires re-recording.",
              ""]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _key_problem(cfg: Config) -> str:
    """Why a config cannot make live calls (empty string if it can)."""
    from backend.config import get_settings

    s = get_settings()
    if cfg.provider == "groq" and not s.GROQ_API_KEY:
        return "GROQ_API_KEY not set"
    if cfg.provider == "anthropic" and not s.ANTHROPIC_API_KEY:
        return "ANTHROPIC_API_KEY not set"
    return ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    ap.add_argument("--split", choices=["dev", "test", "all"], default="test")
    ap.add_argument("--configs", nargs="+", default=DEFAULT_CONFIGS, choices=sorted(CONFIGS))
    ap.add_argument("--out", type=Path, default=DEFAULT_REPORT)
    ap.add_argument("--include-unreviewed", action="store_true",
                    help="score claims whose labels are not human-confirmed; report is stamped PROVISIONAL")
    ap.add_argument("--allow-api", action="store_true",
                    help="allow live Groq/Anthropic/Tavily calls for uncached prompts (spends API quota)")
    ap.add_argument("--dry-run", action="store_true", help="only count uncached API calls per config")
    args = ap.parse_args(argv)

    answers_all = load_answers(args.dataset)
    errs = schema_errors(answers_all)
    if errs:
        print("Dataset schema errors:\n  " + "\n  ".join(errs), file=sys.stderr)
        return 2

    answers = [a for a in answers_all if args.split == "all" or a.split == args.split]
    unreviewed = [a for a in answers if not a.reviewed]
    if unreviewed and not args.include_unreviewed:
        answers = [a for a in answers if a.reviewed]
    provisional = bool(unreviewed) and args.include_unreviewed
    if not answers:
        print(
            f"No reviewed answers in split '{args.split}' "
            f"({len(unreviewed)} unreviewed). Run `python -m backend.eval.review` to confirm labels, "
            "or pass --include-unreviewed for a PROVISIONAL run.",
            file=sys.stderr,
        )
        return 3

    os.environ["SOURCEMD_CALL_CACHE"] = "count" if args.dry_run else ("auto" if args.allow_api else "replay")
    call_cache.reset_cache_state()

    from backend.config import get_settings
    from backend.eval.corpus import CorpusIndex
    from backend.eval.retrieval import EvalRetriever

    print("Loading corpus index...", flush=True)
    retriever = EvalRetriever(CorpusIndex.load())

    runs: list[ConfigRun] = []
    summaries: dict[str, dict] = {}
    for name in args.configs:
        cfg = CONFIGS[name]
        if args.allow_api and not args.dry_run:
            problem = _key_problem(cfg)
            if problem:
                runs.append(ConfigRun(cfg, skipped_reason=problem))
                continue
        call_cache.MISSES.clear()
        try:
            run = run_config(cfg, answers, retriever)
        except call_cache.CacheMiss:
            runs.append(ConfigRun(cfg, skipped_reason="no recorded calls (re-run with --allow-api)"))
            continue
        if args.dry_run:
            print(f"{name}: {dict(call_cache.MISSES) or 'fully cached'}")
            continue
        runs.append(run)
        summaries[name] = summarize(run, answers)
        print(f"{name}: accuracy {summaries[name]['accuracy']:.3f} over {summaries[name]['n_claims']} claims", flush=True)

    if args.dry_run:
        return 0

    settings = get_settings()
    report = render_report(
        runs=runs,
        summaries=summaries,
        retr=retrieval_table(answers, retriever),
        answers=answers,
        split=args.split,
        provisional=provisional,
        models={"groq": settings.GROQ_MODEL, "anthropic": settings.CLAUDE_MODEL},
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8", newline="\n")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
