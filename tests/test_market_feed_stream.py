import asyncio

import pandas as pd

from config.settings import Settings
from src.data.feeds import MarketDataFeed


def test_stream_emits_heartbeat_and_bars(monkeypatch):
    settings = Settings()
    feed = MarketDataFeed(settings)

    index = pd.DatetimeIndex([pd.Timestamp("2026-02-24T10:00:00Z")])
    frame = pd.DataFrame(
        [{"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 10.0}],
        index=index,
    )

    monkeypatch.setattr(feed, "_fetch_with_fallbacks", lambda *args, **kwargs: frame)

    bars = []
    heartbeats = []

    asyncio.run(
        feed.stream(
            ["AAPL"],
            lambda bar: bars.append(bar),
            interval_seconds=0,
            heartbeat_callback=lambda payload: heartbeats.append(payload),
            max_cycles=1,
        )
    )

    assert len(bars) == 1
    assert any(p["event"] == "STREAM_HEARTBEAT" for p in heartbeats)


def test_stream_backoff_and_recovery(monkeypatch):
    settings = Settings()
    feed = MarketDataFeed(settings)

    index = pd.DatetimeIndex([pd.Timestamp("2026-02-24T10:00:00Z")])
    frame = pd.DataFrame(
        [{"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 10.0}],
        index=index,
    )

    calls = {"n": 0}

    def fake_fetch(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("temporary stream failure")
        return frame

    monkeypatch.setattr(feed, "_fetch_with_fallbacks", fake_fetch)

    errors = []
    heartbeats = []

    asyncio.run(
        feed.stream(
            ["AAPL"],
            lambda bar: None,
            interval_seconds=0,
            heartbeat_callback=lambda payload: heartbeats.append(payload),
            error_callback=lambda payload: errors.append(payload),
            backoff_base_seconds=0,
            backoff_max_seconds=0,
            max_cycles=2,
        )
    )

    assert any(p["event"] == "STREAM_SYMBOL_ERROR" for p in errors)
    assert any(p["event"] == "STREAM_BACKOFF" for p in errors)
    assert any(p["event"] == "STREAM_RECOVERED" for p in heartbeats)


def test_stream_raises_after_failure_limit(monkeypatch):
    settings = Settings()
    feed = MarketDataFeed(settings)

    def always_fail(*args, **kwargs):
        raise RuntimeError("down")

    monkeypatch.setattr(feed, "_fetch_with_fallbacks", always_fail)

    events = []

    try:
        asyncio.run(
            feed.stream(
                ["AAPL"],
                lambda bar: None,
                interval_seconds=0,
                error_callback=lambda payload: events.append(payload),
                backoff_base_seconds=0,
                backoff_max_seconds=0,
                max_consecutive_failure_cycles=2,
            )
        )
        raise AssertionError("Expected RuntimeError for stream failure limit")
    except RuntimeError as exc:
        assert "stream_failure_limit_reached" in str(exc)

    assert any(p["event"] == "STREAM_FAILURE_LIMIT_REACHED" for p in events)
