"""Eval metrics, dataset integrity and retrieval fusion."""
from __future__ import annotations

import math

import numpy as np
import pytest

from backend.eval import metrics as M
from backend.eval.corpus import load_pages
from backend.eval.retrieval import rrf_fuse
from backend.eval.schema import load_answers, schema_errors
from backend.eval.validate import evidence_errors

GOLD = ["SUPPORTED", "SUPPORTED", "UNSUPPORTED", "CONTRADICTED", "CONTRADICTED", "SUPPORTED"]
PRED = ["SUPPORTED", "UNSUPPORTED", "UNSUPPORTED", "CONTRADICTED", "SUPPORTED", "SUPPORTED"]


class TestClassificationMetrics:
    def test_accuracy(self):
        assert M.accuracy(GOLD, PRED) == pytest.approx(4 / 6)

    def test_confusion_matrix_rows_are_gold(self):
        m = M.confusion_matrix(GOLD, PRED)
        assert m == [[2, 1, 0], [0, 1, 0], [1, 0, 1]]

    def test_per_class_and_macro_f1(self):
        prf = M.per_class_prf(GOLD, PRED)
        assert prf["SUPPORTED"]["recall"] == pytest.approx(2 / 3)
        assert prf["SUPPORTED"]["precision"] == pytest.approx(2 / 3)
        assert prf["CONTRADICTED"]["recall"] == pytest.approx(0.5)
        assert M.macro_f1(GOLD, PRED) == pytest.approx(np.mean([2 / 3, 2 / 3, 2 / 3]))

    def test_recall_for_label_absent_in_gold_is_nan(self):
        assert math.isnan(M.recall_for(["SUPPORTED"], ["SUPPORTED"], "CONTRADICTED"))

    def test_perfect_and_worst(self):
        assert M.macro_f1(GOLD, GOLD) == 1.0
        assert M.accuracy(GOLD, ["UNSUPPORTED"] * 6) == pytest.approx(1 / 6)


class TestRankMetrics:
    def test_auroc_perfect_inverse_and_chance(self):
        assert M.auroc([0.1, 0.2, 0.8, 0.9], [False, False, True, True]) == 1.0
        assert M.auroc([0.9, 0.8, 0.2, 0.1], [False, False, True, True]) == 0.0
        assert M.auroc([0.5, 0.5, 0.5, 0.5], [False, True, False, True]) == 0.5

    def test_auroc_matches_pairwise_definition(self):
        rng = np.random.default_rng(1)
        s = rng.normal(size=40).round(1)  # rounding forces ties
        y = rng.random(40) > 0.5
        pos, neg = s[y], s[~y]
        expected = np.mean([(p > n) + 0.5 * (p == n) for p in pos for n in neg])
        assert M.auroc(s, y) == pytest.approx(expected)

    def test_auroc_single_class_is_nan(self):
        assert math.isnan(M.auroc([0.1, 0.2], [True, True]))

    def test_spearman_monotone_and_constant(self):
        assert M.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
        assert M.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
        assert math.isnan(M.spearman([1, 1, 1], [1, 2, 3]))


class TestBootstrap:
    def test_ci_brackets_point_estimate_and_is_deterministic(self):
        g, p = np.array(GOLD * 5), np.array(PRED * 5)
        point = M.accuracy(list(g), list(p))
        lo, hi = M.bootstrap_ci(len(g), lambda idx: M.accuracy(list(g[idx]), list(p[idx])), reps=300)
        assert lo <= point <= hi
        again = M.bootstrap_ci(len(g), lambda idx: M.accuracy(list(g[idx]), list(p[idx])), reps=300)
        assert (lo, hi) == again

    def test_too_few_samples_gives_nan(self):
        lo, hi = M.bootstrap_ci(1, lambda idx: 1.0)
        assert math.isnan(lo) and math.isnan(hi)

    def test_fmt_ci(self):
        assert M.fmt_ci(float("nan"), (0.0, 1.0)) == "n/a"
        assert M.fmt_ci(0.5, (0.25, 0.75)) == "0.500 [0.25, 0.75]"


class TestFusion:
    def test_rrf_prefers_items_ranked_by_both(self):
        fused = rrf_fuse([[1, 2, 3], [3, 1, 4]])
        order = [i for i, _ in fused]
        assert order[0] == 1  # rank 1 and 2
        assert set(order) == {1, 2, 3, 4}

    def test_rrf_single_ranking_keeps_order(self):
        assert [i for i, _ in rrf_fuse([[5, 6, 7]])] == [5, 6, 7]


class TestDataset:
    def test_schema_valid(self):
        assert schema_errors(load_answers()) == []

    def test_every_gold_quote_is_on_its_page(self):
        assert evidence_errors(load_answers(), load_pages()) == []

    def test_both_splits_have_all_labels_and_reliable_answers(self):
        answers = load_answers()
        for split in ("dev", "test"):
            subset = [a for a in answers if a.split == split]
            labels = {c.label for a in subset for c in a.claims}
            assert labels == {"SUPPORTED", "UNSUPPORTED", "CONTRADICTED"}
            reliable = sum(a.reliable for a in subset)
            assert 0 < reliable < len(subset), "trust AUROC needs both reliable and unreliable answers"

    def test_claims_are_not_duplicated_across_splits(self):
        answers = load_answers()
        texts = [(c.text, a.split) for a in answers for c in a.claims]
        by_text: dict[str, set[str]] = {}
        for t, s in texts:
            by_text.setdefault(t, set()).add(s)
        assert all(len(v) == 1 for v in by_text.values())

    def test_validator_catches_bad_quote(self):
        answers = load_answers()
        a = next(x for x in answers if x.claims[0].evidence)
        from dataclasses import replace

        bad_ev = replace(a.claims[0].evidence, quote="this sentence is definitely not in the guideline")
        bad = replace(a, claims=[replace(a.claims[0], evidence=bad_ev)])
        assert evidence_errors([bad], load_pages())
