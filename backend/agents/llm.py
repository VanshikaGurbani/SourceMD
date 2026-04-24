"""LLM client helpers used by the agent nodes and RAGAS wrapper.

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

def claude_complete(
    prompt: str,
    *,
    system: str | None = None,
    max_tokens: int = 1024,
    temperature: float = 0.0,
) -> str:
    """Run a single-turn completion and return the text response.

    Routes to Groq (free) when GROQ_API_KEY is set, otherwise falls back
    to Anthropic. Both are called with temperature=0 for deterministic output.
    """
    sys_msg = system or "You are a careful, literal medical fact-checking assistant."
    settings = get_settings()

    if _use_groq():
        client = _get_groq_client()
        resp = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return (resp.choices[0].message.content or "").strip()

    # Anthropic path
    client = _get_anthropic_client()
    msg = client.messages.create(
        model=settings.CLAUDE_MODEL,
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
