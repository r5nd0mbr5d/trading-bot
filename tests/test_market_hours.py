"""Unit tests for market session checks (UK + US, DST-aware)."""

from datetime import datetime, timezone

from src.execution.market_hours import infer_exchange, is_market_open


def test_infer_exchange_lse_suffix():
    assert infer_exchange("HSBA.L") == "LSE"


def test_infer_exchange_defaults_to_us():
    assert infer_exchange("AAPL") == "US"


def test_lse_open_during_london_session_winter():
    # 2024-01-15 09:00 UTC => 09:00 London (GMT), inside 08:00-16:30
    ts = datetime(2024, 1, 15, 9, 0, tzinfo=timezone.utc)
    assert is_market_open("HSBA.L", ts) is True


def test_lse_closed_after_session_winter():
    # 2024-01-15 17:00 UTC => 17:00 London, after close
    ts = datetime(2024, 1, 15, 17, 0, tzinfo=timezone.utc)
    assert is_market_open("HSBA.L", ts) is False


def test_us_open_winter_gmt_conversion():
    # Jan in NYC is EST, 14:45 UTC => 09:45 ET (open)
    ts = datetime(2024, 1, 15, 14, 45, tzinfo=timezone.utc)
    assert is_market_open("AAPL", ts) is True


def test_us_open_summer_bst_conversion():
    # Jul in NYC is EDT, 13:45 UTC => 09:45 ET (open)
    ts = datetime(2024, 7, 15, 13, 45, tzinfo=timezone.utc)
    assert is_market_open("AAPL", ts) is True


def test_us_closed_weekend():
    # Saturday should always be closed.
    ts = datetime(2024, 1, 13, 15, 0, tzinfo=timezone.utc)
    assert is_market_open("AAPL", ts) is False


def test_naive_timestamp_assumed_utc():
    # 2024-01-15 14:45 naive treated as UTC => 09:45 ET (open)
    ts = datetime(2024, 1, 15, 14, 45)
    assert is_market_open("AAPL", ts) is True
