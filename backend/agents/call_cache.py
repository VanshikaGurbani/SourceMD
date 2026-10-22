"""Record/replay cache for external calls (LLM completions, Tavily searches).

Used by the evaluation harness and the test suite so runs are deterministic,
free to repeat and possible offline. Behaviour is chosen with environment
variables, so production is unaffected (default mode is ``off``):

- ``SOURCEMD_CALL_CACHE``      ``off`` (default) | ``record`` | ``replay`` | ``auto``
    * off:    call through, never touch the cache.
    * record: always call through and store the result (overwrites).
    * replay: never call through; a missing entry raises ``CacheMiss``.
    * auto:   replay on a hit, otherwise call through and store the result.
    * count:  dry run: replay hits; on a miss do NOT call, bump ``MISSES`` and
              return the caller's ``placeholder``. Used to estimate API spend.
- ``SOURCEMD_CALL_CACHE_FILE`` path of the JSONL file (default
  ``backend/eval/cache/calls.jsonl``).

Entries are keyed by the SHA-256 of the canonical JSON of the call's inputs,
so any change to a prompt, model or temperature is a different entry.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

DEFAULT_CACHE_FILE = Path(__file__).resolve().parents[1] / "eval" / "cache" / "calls.jsonl"
_VALID_MODES = {"off", "record", "replay", "auto", "count"}

_lock = threading.Lock()
_loaded: dict[Path, dict[str, Any]] = {}
MISSES: dict[str, int] = {}  # kind -> uncached calls seen in ``count`` mode


class CacheMiss(RuntimeError):
    """Raised in replay mode when a call has no recorded result."""


def cache_mode() -> str:
    """Return the active cache mode, validating the env var."""
    mode = os.environ.get("SOURCEMD_CALL_CACHE", "off").strip().lower()
    if mode not in _VALID_MODES:
        raise ValueError(
            f"SOURCEMD_CALL_CACHE must be one of {sorted(_VALID_MODES)}, got {mode!r}"
        )
    return mode


def cache_file() -> Path:
    """Return the JSONL cache path from the environment or the default."""
    override = os.environ.get("SOURCEMD_CALL_CACHE_FILE")
    return Path(override) if override else DEFAULT_CACHE_FILE


def make_key(kind: str, payload: dict[str, Any]) -> str:
    """Return a stable hex digest for a call of type ``kind`` with ``payload``."""
    canonical = json.dumps({"kind": kind, **payload}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    if path not in _loaded:
        entries: dict[str, Any] = {}
        if path.exists():
            with path.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        row = json.loads(line)
                        entries[row["key"]] = row["value"]
        _loaded[path] = entries
    return _loaded[path]


def _append(path: Path, key: str, kind: str, meta: dict[str, Any], value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"key": key, "kind": kind, "meta": meta, "value": value}
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def reset_cache_state() -> None:
    """Forget in-memory entries (tests switch cache files between cases)."""
    with _lock:
        _loaded.clear()
        MISSES.clear()


def cached_call(
    kind: str,
    payload: dict[str, Any],
    fn: Callable[[], Any],
    *,
    meta: dict[str, Any] | None = None,
    placeholder: Any = None,
) -> Any:
    """Run ``fn`` through the record/replay cache and return its JSON-able result.

    ``payload`` must contain every input that can change the result. ``meta`` is
    stored alongside for human inspection only and is not part of the key.
    ``placeholder`` is what ``count`` mode returns for an uncached call.
    """
    mode = cache_mode()
    if mode == "off":
        return fn()

    path = cache_file()
    key = make_key(kind, payload)
    with _lock:
        entries = _load(path)
        if mode in ("replay", "auto", "count") and key in entries:
            return entries[key]
        if mode == "count":
            MISSES[kind] = MISSES.get(kind, 0) + 1
            return placeholder
        if mode == "replay":
            raise CacheMiss(
                f"No recorded {kind} call for key {key[:12]} in {path}. "
                "Re-run with SOURCEMD_CALL_CACHE=auto and API keys to record it."
            )

    value = fn()
    with _lock:
        entries = _load(path)
        entries[key] = value
        _append(path, key, kind, meta or {}, value)
    return value
