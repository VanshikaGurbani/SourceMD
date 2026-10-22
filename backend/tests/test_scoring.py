"""Verdict parsing, trust-score aggregation, quality metrics and the replayed pipeline."""
from __future__ import annotations

import math

import pytest

from backend.agents.nodes.scorer import _aggregate_trust_score, parse_verdict, score_claim, score_claims
from backend.agents.quality_metrics import SOURCE_THRESHOLD, compute_quality_metrics
from backend.tests.fixtures.record_fixtures import ANSWER, CLAIM_1, CLAIM_2, PASSAGE, QUESTION


def _sc(verdict, confidence=0.5, score=0.0):
    src = [{"doc": "d", "page": 1, "chunk": 0, "score": score, "text": "t", "source_url": "", "web_url": ""}]
    return {"text": "c", "verdict": verdict, "confidence": confidence, "rationale": "", "sources": src}


class TestParseVerdict:
    def test_clean_json(self):
        p = parse_verdict('{"verdict": "CONTRADICTED", "confidence": 0.8, "rationale": " r ", "passage": 2, "quote": "q"}')
        assert p == {"verdict": "CONTRADICTED", "confidence": 0.8, "rationale": "r", "passage": 2, "quote": "q"}

    def test_lowercase_verdict_is_normalised(self):
        assert parse_verdict('{"verdict": "supported"}')["verdict"] == "SUPPORTED"

    @pytest.mark.parametrize("raw", ["", "not json", "[1, 2]", '{"verdict": "MAYBE"}', '{"verdict": null}'])
    def test_garbage_or_unknown_verdict_becomes_unsupported(self, raw):
        p = parse_verdict(raw)
        assert p["verdict"] == "UNSUPPORTED"
        assert p["confidence"] == 0.0

    @pytest.mark.parametrize("conf,expected", [(5, 1.0), (-2, 0.0), ("0.4", 0.4), ("high", 0.0), (None, 0.0)])
    def test_confidence_clamped_and_coerced(self, conf, expected):
        import json

        assert parse_verdict(json.dumps({"verdict": "SUPPORTED", "confidence": conf}))["confidence"] == expected

    @pytest.mark.parametrize("passage,expected", [(1, 1), ("2", 2), (None, None), ("abc", None)])
    def test_passage_index(self, passage, expected):
        import json

        assert parse_verdict(json.dumps({"verdict": "SUPPORTED", "passage": passage}))["passage"] == expected


class TestTrustScore:
    def test_empty_is_zero(self):
        assert _aggregate_trust_score([]) == 0.0

    def test_supported_uses_confidence(self):
        assert _aggregate_trust_score([_sc("SUPPORTED", 0.8)]) == 80.0

    def test_unsupported_is_fixed_regardless_of_confidence(self):
        assert _aggregate_trust_score([_sc("UNSUPPORTED", 0.0)]) == 30.0
        assert _aggregate_trust_score([_sc("UNSUPPORTED", 1.0)]) == 30.0

    def test_contradicted_is_zero(self):
        assert _aggregate_trust_score([_sc("CONTRADICTED", 1.0)]) == 0.0

    def test_mean_over_mixed_claims(self):
        scored = [_sc("SUPPORTED", 1.0), _sc("UNSUPPORTED"), _sc("CONTRADICTED")]
        assert _aggregate_trust_score(scored) == pytest.approx((1.0 + 0.3 + 0.0) / 3 * 100, abs=0.01)

    def test_confidence_out_of_range_is_clamped(self):
        assert _aggregate_trust_score([_sc("SUPPORTED", 7.0)]) == 100.0


class TestQualityMetrics:
    def test_no_claims_gives_none(self):
        assert compute_quality_metrics([]) == {"hallucination_rate": None, "source_coverage": None}

    def test_rates(self):
        scored = [
            _sc("SUPPORTED", score=SOURCE_THRESHOLD),
            _sc("UNSUPPORTED", score=0.1),
            _sc("CONTRADICTED", score=0.9),
            _sc("SUPPORTED", score=0.2),
        ]
        m = compute_quality_metrics(scored)
        assert m["hallucination_rate"] == 0.5  # 2 of 4 are non-SUPPORTED (model's own verdicts)
        assert m["source_coverage"] == 0.5  # two have a passage >= threshold

    def test_claim_without_sources_is_not_covered(self):
        sc = _sc("SUPPORTED")
        sc["sources"] = []
        assert compute_quality_metrics([sc])["source_coverage"] == 0.0


class TestReplayedScoring:
    def test_score_claim_from_recorded_response_with_citation(self, replay_llm):
        out = score_claim(CLAIM_1, [PASSAGE])
        assert out["verdict"] == "SUPPORTED"
        assert out["confidence"] == 0.9
        assert out["cited_passage"] == 1
        assert "metformin" in out["quote"]
        assert out["citation_verified"] is True  # quote literally appears in passage 1

    def test_garbage_recorded_response_degrades_to_unsupported(self, replay_llm):
        out = score_claim("Some claim.", [PASSAGE])
        assert out["verdict"] == "UNSUPPORTED"
        assert out["confidence"] == 0.0
        assert out["citation_verified"] is False

    def test_full_scoring_node_replays_all_five_calls(self, replay_llm):
        state = {
            "question": QUESTION,
            "ai_answer": ANSWER,
            "claims": [CLAIM_1, CLAIM_2],
            "retrieved": {CLAIM_1: [PASSAGE], CLAIM_2: [PASSAGE]},
        }
        out = score_claims(state)
        verdicts = [c["verdict"] for c in out["scored_claims"]]
        assert verdicts == ["SUPPORTED", "UNSUPPORTED"]
        # (0.9 + 0.3) / 2 -> 60
        assert math.isclose(out["trust_score"], 60.0)
        assert out["corrected_answer"].startswith("Metformin is offered")
        assert len(out["follow_up_questions"]) == 3
