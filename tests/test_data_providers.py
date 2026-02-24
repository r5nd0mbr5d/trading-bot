"""Unit tests for data provider adapters and factory."""

import json

import pandas as pd
import pytest

from src.data.providers import (
    AlphaVantageProvider,
    NotImplementedProvider,
    PolygonProvider,
    ProviderError,
    YFinanceProvider,
    get_provider,
)


def test_get_provider_returns_yfinance_for_known_aliases():
    assert isinstance(get_provider("yfinance"), YFinanceProvider)
    assert isinstance(get_provider("yf"), YFinanceProvider)
    assert isinstance(get_provider("yahoo"), YFinanceProvider)


def test_get_provider_returns_alpha_vantage_provider():
    provider = get_provider("alpha_vantage")
    assert isinstance(provider, AlphaVantageProvider)


def test_get_provider_returns_scaffold_for_non_implemented_providers():
    provider = get_provider("alpaca")
    assert isinstance(provider, NotImplementedProvider)
    with pytest.raises(NotImplementedError):
        provider.fetch_historical("AAPL")


def test_get_provider_returns_polygon_provider():
    provider = get_provider("polygon")
    assert isinstance(provider, PolygonProvider)


def test_polygon_provider_returns_utc_frame(monkeypatch):
    payload = {
        "status": "OK",
        "results": [
            {
                "t": 1704067200000,
                "o": 100.0,
                "h": 101.0,
                "l": 99.5,
                "c": 100.5,
                "v": 12000,
            }
        ],
    }

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    captured = {}

    def fake_urlopen(url, timeout):
        captured["url"] = url
        captured["timeout"] = timeout
        return _Resp()

    monkeypatch.setenv("POLYGON_API_KEY", "test-key")
    monkeypatch.setattr("src.data.providers.urlopen", fake_urlopen)

    provider = PolygonProvider()
    result = provider.fetch_historical("VOD.L", start="2024-01-01", end="2024-01-03")

    assert "apiKey=test-key" in captured["url"]
    assert "/v2/aggs/ticker/VOD.L/range/1/day/2024-01-01/2024-01-03" in captured["url"]
    assert result.index.tz is not None
    assert str(result.index.tz) == "UTC"
    assert list(result.columns) == ["open", "high", "low", "close", "volume"]


def test_polygon_provider_raises_provider_error_without_api_key(monkeypatch):
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    provider = PolygonProvider(api_key="")
    with pytest.raises(ProviderError):
        provider.fetch_historical("AAPL", start="2024-01-01", end="2024-01-02")


def test_unknown_provider_defaults_to_yfinance():
    assert isinstance(get_provider("unknown-provider"), YFinanceProvider)


def test_yfinance_provider_calls_ticker_history(monkeypatch):
    index = pd.DatetimeIndex(["2024-01-01"], tz="UTC")
    expected = pd.DataFrame(
        {
            "Open": [1.0],
            "High": [1.1],
            "Low": [0.9],
            "Close": [1.05],
            "Volume": [1000],
        },
        index=index,
    )

    class FakeTicker:
        def history(self, **kwargs):
            return expected

    monkeypatch.setattr("src.data.providers.yf.Ticker", lambda symbol: FakeTicker())

    provider = YFinanceProvider()
    result = provider.fetch_historical("AAPL", period="1d", interval="1m")
    assert result.equals(expected)
