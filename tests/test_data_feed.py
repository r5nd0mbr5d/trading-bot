"""Unit tests for market data feed timestamp handling."""

from datetime import timezone

import pandas as pd

from config.settings import Settings
from src.data.feeds import MarketDataFeed


def _sample_df(index):
    return pd.DataFrame(
        {
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.5, 100.5],
            "close": [100.5, 101.5],
            "volume": [1_000, 1_100],
        },
        index=index,
    )


def test_fetch_historical_converts_tz_aware_index_to_utc(monkeypatch):
    eastern_index = pd.DatetimeIndex(
        ["2024-01-01 09:30:00", "2024-01-01 09:31:00"],
        tz="America/New_York",
    )

    class FakeTicker:
        def history(self, **kwargs):
            return _sample_df(eastern_index)

    monkeypatch.setattr("src.data.providers.yf.Ticker", lambda symbol: FakeTicker())

    settings = Settings()
    settings.data.cache_enabled = False
    feed = MarketDataFeed(settings)
    df = feed.fetch_historical("AAPL", period="1d", interval="1m")

    assert df.index.tz is not None
    assert str(df.index.tz) == "UTC"


def test_fetch_historical_localizes_naive_index_to_utc(monkeypatch):
    naive_index = pd.DatetimeIndex(["2024-01-01", "2024-01-02"])

    class FakeTicker:
        def history(self, **kwargs):
            return _sample_df(naive_index)

    monkeypatch.setattr("src.data.providers.yf.Ticker", lambda symbol: FakeTicker())

    settings = Settings()
    settings.data.cache_enabled = False
    feed = MarketDataFeed(settings)
    df = feed.fetch_historical("MSFT", period="5d", interval="1d")

    assert df.index.tz is not None
    assert str(df.index.tz) == "UTC"


def test_fetch_historical_logs_warning_on_naive_index(monkeypatch, caplog):
    naive_index = pd.DatetimeIndex(["2024-01-01", "2024-01-02"])

    class FakeTicker:
        def history(self, **kwargs):
            return _sample_df(naive_index)

    monkeypatch.setattr("src.data.providers.yf.Ticker", lambda symbol: FakeTicker())

    settings = Settings()
    settings.data.cache_enabled = False
    feed = MarketDataFeed(settings)
    with caplog.at_level("WARNING"):
        feed.fetch_historical("VOD.L", period="5d", interval="1d")

    assert "naive timestamps" in caplog.text


def test_fetch_historical_uses_fallback_provider(monkeypatch):
    class FailingProvider:
        def fetch_historical(self, **kwargs):
            raise RuntimeError("primary down")

    class WorkingProvider:
        def fetch_historical(self, **kwargs):
            idx = pd.DatetimeIndex(["2024-01-01", "2024-01-02"], tz="UTC")
            return _sample_df(idx)

    settings = Settings()
    settings.data.source = "yfinance"
    settings.data.fallback_sources = ["polygon"]

    settings.data.cache_enabled = False
    feed = MarketDataFeed(settings)
    feed._primary_provider = FailingProvider()
    feed._fallback_providers = [WorkingProvider()]

    df = feed.fetch_historical("AAPL", period="1d", interval="1m")
    assert not df.empty
    assert str(df.index.tz) == "UTC"


def test_to_bars_emits_utc_aware_timestamps():
    utc_index = pd.DatetimeIndex(["2024-01-01 00:00:00", "2024-01-02 00:00:00"], tz="UTC")
    df = _sample_df(utc_index)

    settings = Settings()
    settings.data.cache_enabled = False
    feed = MarketDataFeed(settings)
    bars = feed.to_bars("AAPL", df)

    assert len(bars) == 2
    assert bars[0].timestamp.tzinfo is not None
    assert bars[0].timestamp.tzinfo == timezone.utc
