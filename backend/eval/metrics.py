"""Evaluation metrics: classification, AUROC, rank correlation, bootstrap CIs.

Pure numpy; no sklearn dependency so CI stays light.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np

from backend.eval.schema import LABELS


def confusion_matrix(
    gold: Sequence[str], pred: Sequence[str], labels: Sequence[str] = LABELS
) -> list[list[int]]:
    """Rows = gold label, columns = predicted label, in ``labels`` order."""
    idx = {lab: i for i, lab in enumerate(labels)}
    m = [[0] * len(labels) for _ in labels]
    for g, p in zip(gold, pred, strict=True):
        m[idx[g]][idx[p]] += 1
    return m


def accuracy(gold: Sequence[str], pred: Sequence[str]) -> float:
    """Share of predictions equal to gold; NaN for empty input."""
    if not gold:
        return float("nan")
    return sum(g == p for g, p in zip(gold, pred, strict=True)) / len(gold)


def per_class_prf(
    gold: Sequence[str], pred: Sequence[str], labels: Sequence[str] = LABELS
) -> dict[str, dict[str, float]]:
    """Precision/recall/F1/support per label. Undefined ratios are 0.0, support 0 -> excluded by caller."""
    out: dict[str, dict[str, float]] = {}
    for lab in labels:
        tp = sum(1 for g, p in zip(gold, pred, strict=True) if g == lab and p == lab)
        fp = sum(1 for g, p in zip(gold, pred, strict=True) if g != lab and p == lab)
        fn = sum(1 for g, p in zip(gold, pred, strict=True) if g == lab and p != lab)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        out[lab] = {"precision": prec, "recall": rec, "f1": f1, "support": float(tp + fn)}
    return out


def macro_f1(
    gold: Sequence[str], pred: Sequence[str], labels: Sequence[str] = LABELS
) -> float:
    """Unweighted mean F1 over labels that occur in ``gold``."""
    prf = per_class_prf(gold, pred, labels)
    present = [prf[lab]["f1"] for lab in labels if prf[lab]["support"] > 0]
    return float(np.mean(present)) if present else float("nan")


def recall_for(gold: Sequence[str], pred: Sequence[str], label: str) -> float:
    """Recall of one label; NaN if the label never occurs in ``gold``."""
    support = sum(1 for g in gold if g == label)
    if support == 0:
        return float("nan")
    hits = sum(1 for g, p in zip(gold, pred, strict=True) if g == label and p == label)
    return hits / support


def _average_ranks(values: np.ndarray) -> np.ndarray:
    """Ranks starting at 1 with ties assigned their average rank."""
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=float)
    sorted_vals = values[order]
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and sorted_vals[j + 1] == sorted_vals[i]:
            j += 1
        ranks[order[i : j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return ranks


def auroc(scores: Sequence[float], positive: Sequence[bool]) -> float:
    """Area under the ROC curve via the Mann-Whitney U statistic (ties count 0.5).

    NaN when only one class is present, since AUROC is undefined there.
    """
    s = np.asarray(scores, dtype=float)
    y = np.asarray(positive, dtype=bool)
    n_pos = int(y.sum())
    n_neg = int((~y).sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    ranks = _average_ranks(s)
    u = ranks[y].sum() - n_pos * (n_pos + 1) / 2.0
    return float(u / (n_pos * n_neg))


def spearman(x: Sequence[float], y: Sequence[float]) -> float:
    """Spearman rank correlation; NaN if either input is constant or too short."""
    a = np.asarray(x, dtype=float)
    b = np.asarray(y, dtype=float)
    if len(a) < 3 or np.all(a == a[0]) or np.all(b == b[0]):
        return float("nan")
    ra, rb = _average_ranks(a), _average_ranks(b)
    return float(np.corrcoef(ra, rb)[0, 1])


def bootstrap_ci(
    n: int,
    stat: Callable[[np.ndarray], float],
    *,
    reps: int = 2000,
    seed: int = 0,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Percentile bootstrap CI for ``stat`` over resampled indices ``0..n-1``.

    ``stat`` receives an integer index array and returns a float (NaN results
    from degenerate resamples are dropped). Returns (nan, nan) if ``n`` < 2.
    """
    if n < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    vals: list[float] = []
    for _ in range(reps):
        idx = rng.integers(0, n, size=n)
        v = stat(idx)
        if not np.isnan(v):
            vals.append(v)
    if not vals:
        return float("nan"), float("nan")
    lo, hi = np.quantile(vals, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi)


def fmt_ci(value: float, ci: tuple[float, float]) -> str:
    """Format ``0.812 [0.70, 0.91]`` (or ``n/a`` when undefined)."""
    if np.isnan(value):
        return "n/a"
    if np.isnan(ci[0]):
        return f"{value:.3f}"
    return f"{value:.3f} [{ci[0]:.2f}, {ci[1]:.2f}]"
