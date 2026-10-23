"""JSON extraction, claim-extraction parsing and fallbacks, replayed from fixtures."""
from __future__ import annotations

import pytest

from backend.agents.call_cache import CacheMiss
from backend.agents.llm import extract_json
from backend.agents.nodes.claim_extractor import extract_claims
from backend.tests.fixtures.record_fixtures import ANSWER, CLAIM_1, CLAIM_2, QUESTION


class TestExtractJson:
    def test_raw_array(self):
        assert extract_json('["a", "b"]') == ["a", "b"]

    def test_fenced_json(self):
        assert extract_json('```json\n{"x": 1}\n```') == {"x": 1}

    def test_json_embedded_in_prose(self):
        assert extract_json('Sure! Here you go: {"verdict": "SUPPORTED"} hope that helps') == {
            "verdict": "SUPPORTED"
        }

    def test_array_preferred_over_object_in_prose(self):
        assert extract_json('claims: ["a"]') == ["a"]

    @pytest.mark.parametrize("bad", ["", "   ", "no json here", "{broken"])
    def test_unparseable_raises(self, bad):
        with pytest.raises(ValueError):
            extract_json(bad)


class TestExtractClaims:
    def test_parses_fenced_array_from_recorded_response(self, replay_llm):
        out = extract_claims({"question": QUESTION, "ai_answer": ANSWER})
        assert out == {"claims": [CLAIM_1, CLAIM_2]}

    def test_malformed_response_falls_back_to_whole_answer(self, replay_llm):
        out = extract_claims({"question": QUESTION, "ai_answer": "foo bar baz"})
        assert out == {"claims": ["foo bar baz"]}

    def test_replay_miss_is_loud(self, replay_llm):
        with pytest.raises(CacheMiss):
            extract_claims({"question": QUESTION, "ai_answer": "an answer with no recorded call"})

    def test_blank_and_non_string_items_are_cleaned(self, monkeypatch):
        monkeypatch.setattr(
            "backend.agents.nodes.claim_extractor.claude_complete",
            lambda *a, **k: '["  keep me  ", "", "   ", 42]',
        )
        out = extract_claims({"question": QUESTION, "ai_answer": "x"})
        assert out == {"claims": ["keep me", "42"]}

    def test_non_list_json_becomes_single_claim(self, monkeypatch):
        monkeypatch.setattr(
            "backend.agents.nodes.claim_extractor.claude_complete", lambda *a, **k: '{"a": 1}'
        )
        out = extract_claims({"question": QUESTION, "ai_answer": "x"})
        assert len(out["claims"]) == 1

    def test_empty_array_falls_back_to_answer(self, monkeypatch):
        monkeypatch.setattr(
            "backend.agents.nodes.claim_extractor.claude_complete", lambda *a, **k: "[]"
        )
        assert extract_claims({"question": QUESTION, "ai_answer": "the answer"}) == {
            "claims": ["the answer"]
        }
