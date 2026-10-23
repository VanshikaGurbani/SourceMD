"""Provider routing and Groq -> Anthropic failover."""
from __future__ import annotations

import pytest

from backend.agents import llm
from backend.config import get_settings


@pytest.fixture
def calls(monkeypatch):
    seen: list[str] = []

    def fake_raw(provider, model, sys_msg, prompt, max_tokens, temperature):
        seen.append(provider)
        if provider == "groq":
            raise RuntimeError("model_not_found")
        return "from-anthropic"

    monkeypatch.setattr(llm, "_raw_complete", fake_raw)
    return seen


def _keys(monkeypatch, groq: str, anthropic: str, failover: bool = True):
    s = get_settings()
    monkeypatch.setattr(s, "LLM_FAILOVER", failover)
    monkeypatch.setattr(s, "GROQ_API_KEY", groq)
    monkeypatch.setattr(s, "ANTHROPIC_API_KEY", anthropic)


def test_fails_over_to_anthropic_when_groq_errors_and_both_keys_set(monkeypatch, calls):
    _keys(monkeypatch, "g", "a")
    assert llm.claude_complete("hi") == "from-anthropic"
    assert calls == ["groq", "anthropic"]


def test_no_failover_without_anthropic_key(monkeypatch, calls):
    _keys(monkeypatch, "g", "")
    with pytest.raises(RuntimeError, match="model_not_found"):
        llm.claude_complete("hi")
    assert calls == ["groq"]


def test_explicit_provider_never_fails_over(monkeypatch, calls):
    _keys(monkeypatch, "g", "a")
    with pytest.raises(RuntimeError):
        llm.claude_complete("hi", provider="groq")
    assert calls == ["groq"]


def test_anthropic_only_routes_to_anthropic(monkeypatch, calls):
    _keys(monkeypatch, "", "a")
    assert llm.claude_complete("hi") == "from-anthropic"
    assert calls == ["anthropic"]


def test_failover_is_off_unless_enabled(monkeypatch, calls):
    _keys(monkeypatch, "g", "a", failover=False)
    with pytest.raises(RuntimeError):
        llm.claude_complete("hi")
    assert calls == ["groq"]
