"""Provider routing, Groq model fallbacks, rate-limit handling and Anthropic failover."""
from __future__ import annotations

import pytest
from openai import RateLimitError

from backend.agents import llm
from backend.agents.llm import LLMBusyError
from backend.config import get_settings


class _RateLimited(RateLimitError):
    def __init__(self):  # noqa: D107 - bypass the SDK's response requirement
        Exception.__init__(self, "rate limited")


@pytest.fixture
def calls(monkeypatch):
    seen: list[tuple[str, str]] = []

    def fake_raw(provider, model, sys_msg, prompt, max_tokens, temperature):
        seen.append((provider, model))
        if provider == "groq":
            raise RuntimeError("model_not_found")
        return "from-anthropic"

    monkeypatch.setattr(llm, "_raw_complete", fake_raw)
    return seen


def _keys(monkeypatch, groq: str, anthropic: str, failover: bool = True, fallbacks: str = ""):
    s = get_settings()
    monkeypatch.setattr(s, "LLM_FAILOVER", failover)
    monkeypatch.setattr(s, "GROQ_API_KEY", groq)
    monkeypatch.setattr(s, "ANTHROPIC_API_KEY", anthropic)
    monkeypatch.setattr(s, "GROQ_FALLBACK_MODELS", fallbacks)


def test_fails_over_to_anthropic_when_groq_errors_and_both_keys_set(monkeypatch, calls):
    _keys(monkeypatch, "g", "a")
    assert llm.claude_complete("hi") == "from-anthropic"
    assert [p for p, _ in calls] == ["groq", "anthropic"]


def test_no_failover_without_anthropic_key(monkeypatch, calls):
    _keys(monkeypatch, "g", "")
    with pytest.raises(RuntimeError, match="model_not_found"):
        llm.claude_complete("hi")
    assert [p for p, _ in calls] == ["groq"]


def test_explicit_provider_never_fails_over(monkeypatch, calls):
    _keys(monkeypatch, "g", "a", fallbacks="other-model")
    with pytest.raises(RuntimeError):
        llm.claude_complete("hi", provider="groq")
    assert len(calls) == 1  # no fallback models, no Anthropic


def test_anthropic_only_routes_to_anthropic(monkeypatch, calls):
    _keys(monkeypatch, "", "a")
    assert llm.claude_complete("hi") == "from-anthropic"
    assert [p for p, _ in calls] == ["anthropic"]


def test_failover_is_off_unless_enabled(monkeypatch, calls):
    _keys(monkeypatch, "g", "a", failover=False)
    with pytest.raises(RuntimeError):
        llm.claude_complete("hi")
    assert [p for p, _ in calls] == ["groq"]


def test_uses_free_fallback_model_when_primary_fails(monkeypatch):
    seen: list[str] = []

    def fake_raw(provider, model, sys_msg, prompt, max_tokens, temperature):
        seen.append(model)
        if model == "primary":
            raise _RateLimited()
        return f"answer from {model}"

    monkeypatch.setattr(llm, "_raw_complete", fake_raw)
    _keys(monkeypatch, "g", "", fallbacks="second,third")
    monkeypatch.setattr(get_settings(), "GROQ_MODEL", "primary")
    assert llm.claude_complete("hi") == "answer from second"
    assert seen == ["primary", "second"]


def test_all_models_rate_limited_raises_busy_error(monkeypatch):
    def fake_raw(*args, **kwargs):
        raise _RateLimited()

    monkeypatch.setattr(llm, "_raw_complete", fake_raw)
    _keys(monkeypatch, "g", "", fallbacks="second")
    with pytest.raises(LLMBusyError):
        llm.claude_complete("hi")


def test_busy_error_becomes_503_from_the_api(monkeypatch):
    from fastapi.testclient import TestClient

    from backend.main import create_app

    def busy(*_a, **_k):
        raise LLMBusyError("The AI model is at its free-tier limit right now. Please try again in a minute.")

    monkeypatch.setattr("backend.api.routes.followup.claude_complete", busy)
    r = TestClient(create_app()).post(
        "/follow-up",
        json={"question": "why?", "original_question": "q q q", "ai_answer": "a", "corrected_answer": "c"},
    )
    assert r.status_code == 503
    assert "free-tier limit" in r.json()["detail"]
