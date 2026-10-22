"""Record/replay cache behaviour and the literal-quote citation check."""
from __future__ import annotations

import pytest

from backend.agents import call_cache
from backend.agents.citations import quote_in, verify_citation


@pytest.fixture
def cache_file(tmp_path, monkeypatch):
    path = tmp_path / "calls.jsonl"
    monkeypatch.setenv("SOURCEMD_CALL_CACHE_FILE", str(path))
    call_cache.reset_cache_state()
    return path


class TestCallCache:
    def test_off_always_calls_through(self, cache_file):
        calls = []
        for _ in range(2):
            call_cache.cached_call("llm", {"p": 1}, lambda: calls.append(1) or "x")
        assert len(calls) == 2
        assert not cache_file.exists()

    def test_auto_records_then_replays(self, cache_file, monkeypatch):
        monkeypatch.setenv("SOURCEMD_CALL_CACHE", "auto")
        calls = []
        first = call_cache.cached_call("llm", {"p": 1}, lambda: calls.append(1) or "answer")
        second = call_cache.cached_call("llm", {"p": 1}, lambda: calls.append(1) or "different")
        assert (first, second) == ("answer", "answer")
        assert len(calls) == 1
        assert cache_file.read_text(encoding="utf-8").count("\n") == 1

    def test_persists_across_process_state_reset(self, cache_file, monkeypatch):
        monkeypatch.setenv("SOURCEMD_CALL_CACHE", "auto")
        call_cache.cached_call("llm", {"p": 1}, lambda: "kept")
        call_cache.reset_cache_state()
        monkeypatch.setenv("SOURCEMD_CALL_CACHE", "replay")
        assert call_cache.cached_call("llm", {"p": 1}, lambda: pytest.fail("must not call")) == "kept"

    def test_replay_miss_raises(self, cache_file, monkeypatch):
        monkeypatch.setenv("SOURCEMD_CALL_CACHE", "replay")
        with pytest.raises(call_cache.CacheMiss):
            call_cache.cached_call("llm", {"p": 2}, lambda: "never")

    def test_any_payload_change_is_a_different_key(self):
        a = call_cache.make_key("llm", {"prompt": "x", "temperature": 0.0})
        assert a != call_cache.make_key("llm", {"prompt": "x", "temperature": 0.3})
        assert a != call_cache.make_key("tavily", {"prompt": "x", "temperature": 0.0})
        assert a == call_cache.make_key("llm", {"temperature": 0.0, "prompt": "x"})

    def test_count_mode_counts_misses_without_calling(self, cache_file, monkeypatch):
        monkeypatch.setenv("SOURCEMD_CALL_CACHE", "count")
        out = call_cache.cached_call("llm", {"p": 3}, lambda: pytest.fail("must not call"), placeholder="{}")
        assert out == "{}"
        assert call_cache.MISSES == {"llm": 1}

    def test_invalid_mode_is_rejected(self, monkeypatch):
        monkeypatch.setenv("SOURCEMD_CALL_CACHE", "bogus")
        with pytest.raises(ValueError):
            call_cache.cache_mode()


PASSAGES = [
    {"doc": "d", "page": 1, "chunk": 0, "score": 0.5, "source_url": "", "web_url": "",
     "text": "Offer an ACE inhibitor or an ARB to adults starting step 1 antihyper-\ntensive treatment."},
    {"doc": "d", "page": 2, "chunk": 0, "score": 0.4, "source_url": "", "web_url": "", "text": "Unrelated text."},
]


class TestCitations:
    def test_literal_match_ignores_case_whitespace_and_hyphenation(self):
        assert quote_in("offer an ace inhibitor or an arb", PASSAGES[0]["text"])
        assert quote_in("step 1 antihypertensive treatment", PASSAGES[0]["text"])

    def test_changed_number_is_not_a_match(self):
        assert not quote_in("step 2 antihypertensive treatment", PASSAGES[0]["text"])

    def test_empty_quote_never_matches(self):
        assert not quote_in("", "anything")

    def test_verify_citation_needs_valid_index_and_quote(self):
        assert verify_citation("ACE inhibitor or an ARB", 1, PASSAGES)
        assert not verify_citation("ACE inhibitor or an ARB", 2, PASSAGES)  # quote is in passage 1, not 2
        assert not verify_citation("ACE inhibitor", None, PASSAGES)
        assert not verify_citation("ACE inhibitor", 3, PASSAGES)
        assert not verify_citation("ACE inhibitor", 0, PASSAGES)
