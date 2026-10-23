"""Shared pytest setup: offline, deterministic, no real services."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

# Must be set before backend.config / backend.db.base are imported anywhere.
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ["GROQ_API_KEY"] = "test-key-not-real"
os.environ["GROQ_MODEL"] = "test-model"  # pinned so fixtures do not depend on the production default
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["TAVILY_API_KEY"] = ""
os.environ["SOURCEMD_CALL_CACHE"] = "off"
os.environ["SOURCEMD_WAKE_CHROMA"] = "0"  # no background network pings in tests

FIXTURES = Path(__file__).parent / "fixtures"
LLM_FIXTURE_FILE = FIXTURES / "llm_calls.jsonl"


@pytest.fixture(autouse=True)
def _reset_call_cache(monkeypatch):
    """Every test starts with the call cache off and its in-memory state cleared."""
    from backend.agents import call_cache

    monkeypatch.setenv("SOURCEMD_CALL_CACHE", "off")
    monkeypatch.delenv("SOURCEMD_CALL_CACHE_FILE", raising=False)
    call_cache.reset_cache_state()
    yield
    call_cache.reset_cache_state()


@pytest.fixture
def replay_llm(monkeypatch):
    """Serve LLM/Tavily calls from the committed fixture file; a miss raises CacheMiss."""
    from backend.agents import call_cache

    monkeypatch.setenv("SOURCEMD_CALL_CACHE", "replay")
    monkeypatch.setenv("SOURCEMD_CALL_CACHE_FILE", str(LLM_FIXTURE_FILE))
    call_cache.reset_cache_state()
    return LLM_FIXTURE_FILE
