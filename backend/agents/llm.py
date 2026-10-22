"""LLM client helpers used by the agent nodes.

Supports two backends selected at startup:
- Groq  (free tier)  — used when GROQ_API_KEY is set in .env
- Anthropic (paid)   — fallback when ANTHROPIC_API_KEY is set

Both expose the same ``llm_complete`` function so the rest of the
codebase is backend-agnostic.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import cast

from backend.agents.call_cache import cache_mode, cached_call
from backend.config import get_settings

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------

def _use_groq() -> bool:
    """Return True if a Groq API key is configured."""
    return bool(get_settings().GROQ_API_KEY)


@lru_cache(maxsize=1)
def _get_groq_client():
    """Return a cached OpenAI-SDK client pointed at the Groq endpoint."""
    from openai import OpenAI  # noqa: WPS433
    settings = get_settings()
    if not settings.GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to backend/.env and rebuild."
        )
    return OpenAI(
        api_key=settings.GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
    )


@lru_cache(maxsize=1)
def _get_anthropic_client():
    """Return a cached Anthropic SDK client."""
    from anthropic import Anthropic  # noqa: WPS433
    settings = get_settings()
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to backend/.env and rebuild."
        )
    return Anthropic(api_key=settings.ANTHROPIC_API_KEY)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def resolve_provider(provider: str | None = None) -> tuple[str, str]:
    """Return ``(provider, model)`` for a request.

    ``provider`` may be ``"groq"`` or ``"anthropic"``; ``None`` keeps the
    production rule (Groq when GROQ_API_KEY is set, otherwise Anthropic).
    In call-cache replay mode no key is needed, so the default is Groq.
    """
    settings = get_settings()
    if provider is None:
        replaying = cache_mode() in ("replay", "count")
        provider = "groq" if (_use_groq() or replaying) else "anthropic"
    if provider == "groq":
        return "groq", settings.GROQ_MODEL
    if provider == "anthropic":
        return "anthropic", settings.CLAUDE_MODEL
    raise ValueError(f"Unknown LLM provider: {provider!r}")


def _raw_complete(
    provider: str,
    model: str,
    sys_msg: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
) -> str:
    """Make one real API call to ``provider`` and return the text."""
    if provider == "groq":
        client = _get_groq_client()
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return (resp.choices[0].message.content or "").strip()

    client = _get_anthropic_client()
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=sys_msg,
        messages=[{"role": "user", "content": prompt}],
    )
    parts: list[str] = []
    for block in msg.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts).strip()


def claude_complete(
    prompt: str,
    *,
    system: str | None = None,
    max_tokens: int = 1024,
    temperature: float = 0.0,
    provider: str | None = None,
) -> str:
    """Run a single-turn completion and return the text response.

    Routes to Groq (free) when GROQ_API_KEY is set, otherwise falls back
    to Anthropic; ``provider`` forces one explicitly (used by the eval
    ablations). Calls go through the record/replay cache, which is a no-op
    unless SOURCEMD_CALL_CACHE is set.
    """
    sys_msg = system or "You are a careful, literal medical fact-checking assistant."
    resolved, model = resolve_provider(provider)
    payload = {
        "provider": resolved,
        "model": model,
        "system": sys_msg,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    return cast(
        str,
        cached_call(
            "llm",
            payload,
            lambda: _raw_complete(resolved, model, sys_msg, prompt, max_tokens, temperature),
            meta={"provider": resolved, "model": model},
            placeholder="{}",
        ),
    )


def extract_json(text: str) -> object:
    """Extract a JSON object or array from an LLM response.

    Handles three common shapes: raw JSON, JSON inside a ```json fence, and
    JSON embedded in prose. Raises ValueError if nothing parseable is found.
    """
    text = text.strip()
    if not text:
        raise ValueError("Empty response from LLM")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fence = _JSON_FENCE.search(text)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass

    for opener, closer in (("[", "]"), ("{", "}")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            chunk = text[start : end + 1]
            try:
                return json.loads(chunk)
            except json.JSONDecodeError:
                continue

    raise ValueError(f"Could not parse JSON from LLM response: {text[:200]}")
