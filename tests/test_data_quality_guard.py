"""Tests for data quality guard."""

from datetime import datetime, timedelta, timezone

from src.risk.data_quality import DataQualityGuard


def test_stale_bar_triggers_consecutive_limit():
    guard = DataQualityGuard(max_bar_age_seconds=60, max_consecutive_stale=2)
    now = datetime(2026, 2, 23, 12, 0, tzinfo=timezone.utc)
    stale_ts = now - timedelta(seconds=120)

    reasons1 = guard.check_bar("AAPL", stale_ts, now)
    assert "stale_bar_age_seconds" in reasons1[0]

    reasons2 = guard.check_bar("AAPL", stale_ts, now)
    assert "stale_data_max_consecutive" in reasons2


def test_session_gap_skip_bar():
    guard = DataQualityGuard(max_bar_gap_seconds=300, session_gap_skip_bars=1)
    now = datetime(2026, 2, 23, 12, 0, tzinfo=timezone.utc)
    ts1 = now - timedelta(minutes=10)
    ts2 = now

    guard.check_bar("AAPL", ts1, now)
    reasons = guard.check_bar("AAPL", ts2, now)

    assert "session_gap_skip_bar" in reasons
