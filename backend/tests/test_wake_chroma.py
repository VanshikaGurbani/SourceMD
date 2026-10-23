"""The background ChromaDB wake-up ping."""
from __future__ import annotations

import time

import httpx

from backend.agents import chroma_client


def test_wake_pings_once_per_interval(monkeypatch):
    monkeypatch.setenv("SOURCEMD_WAKE_CHROMA", "1")
    monkeypatch.setattr(chroma_client, "_last_wake", float("-inf"))
    seen: list[str] = []
    monkeypatch.setattr(httpx, "get", lambda url, timeout: seen.append(url))
    chroma_client.wake_chroma_async()
    chroma_client.wake_chroma_async()  # inside the interval: ignored
    time.sleep(0.2)
    assert len(seen) == 1
    assert seen[0].endswith("/api/v1/heartbeat")


def test_wake_can_be_disabled_and_never_raises(monkeypatch):
    monkeypatch.setenv("SOURCEMD_WAKE_CHROMA", "0")
    monkeypatch.setattr(chroma_client, "_last_wake", float("-inf"))
    chroma_client.wake_chroma_async()
    monkeypatch.setenv("SOURCEMD_WAKE_CHROMA", "1")

    def boom(url, timeout):
        raise RuntimeError("down")

    monkeypatch.setattr(httpx, "get", boom)
    chroma_client.wake_chroma_async()  # the thread swallows the error
    time.sleep(0.1)


def test_first_ping_is_sent_even_when_the_clock_is_young(monkeypatch):
    """Regression: a monotonic clock under the interval must not suppress the first ping."""
    monkeypatch.setenv("SOURCEMD_WAKE_CHROMA", "1")
    monkeypatch.setattr(chroma_client, "_last_wake", float("-inf"))
    monkeypatch.setattr(chroma_client.time, "monotonic", lambda: 5.0)
    seen: list[str] = []
    monkeypatch.setattr(httpx, "get", lambda url, timeout: seen.append(url))
    chroma_client.wake_chroma_async()
    time.sleep(0.2)
    assert len(seen) == 1


def test_retry_window_covers_a_slow_wake():
    assert sum(chroma_client.BACKOFF_SECONDS) >= 100
