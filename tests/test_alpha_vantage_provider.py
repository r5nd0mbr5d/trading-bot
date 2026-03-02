import json
from urllib.error import HTTPError

import pytest

from src.data.providers import AlphaVantageProvider, ProviderError


def _sample_payload():
    return {
        "Meta Data": {"1. Information": "Daily Prices"},
        "Time Series (Daily)": {
            "2024-01-02": {
                "1. open": "100.0",
                "2. high": "101.0",
                "3. low": "99.5",
                "4. close": "100.5",
                "5. volume": "12000",
            },
            "2024-01-01": {
                "1. open": "98.0",
                "2. high": "99.0",
                "3. low": "97.5",
                "4. close": "98.5",
                "5. volume": "11000",
            },
        },
    }


def test_alpha_vantage_provider_returns_utc_frame(monkeypatch):
    payload = _sample_payload()

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    def fake_urlopen(url, timeout):
        return _Resp()

    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "test-key")
    monkeypatch.setattr("src.data.providers.urlopen", fake_urlopen)

    provider = AlphaVantageProvider()
    result = provider.fetch_historical("AAPL", start="2024-01-01", end="2024-01-02")

    assert result.index.tz is not None
    assert str(result.index.tz) == "UTC"
    assert list(result.columns) == ["open", "high", "low", "close", "volume"]
    assert len(result) == 2


def test_alpha_vantage_provider_retries_on_429(monkeypatch):
    payload = _sample_payload()
    calls = {"count": 0}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    def fake_urlopen(url, timeout):
        calls["count"] += 1
        if calls["count"] < 3:
            raise HTTPError(url, 429, "Too Many Requests", None, None)
        return _Resp()

    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "test-key")
    monkeypatch.setattr("src.data.providers.urlopen", fake_urlopen)
    monkeypatch.setattr("src.data.providers.time.sleep", lambda *_: None)

    provider = AlphaVantageProvider(max_retries=3, backoff_base_seconds=0.0)
    result = provider.fetch_historical("AAPL", start="2024-01-01", end="2024-01-02")

    assert len(result) == 2
    assert calls["count"] == 3


def test_alpha_vantage_provider_raises_on_missing_series(monkeypatch):
    payload = {"Meta Data": {"1. Information": "Daily Prices"}}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "test-key")
    monkeypatch.setattr("src.data.providers.urlopen", lambda url, timeout: _Resp())

    provider = AlphaVantageProvider()
    with pytest.raises(ProviderError):
        provider.fetch_historical("AAPL")


def test_alpha_vantage_provider_raises_on_invalid_json(monkeypatch):
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"{ invalid json }"

    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "test-key")
    monkeypatch.setattr("src.data.providers.urlopen", lambda url, timeout: _Resp())

    provider = AlphaVantageProvider()
    with pytest.raises(ProviderError):
        provider.fetch_historical("AAPL")


def test_alpha_vantage_provider_requires_api_key(monkeypatch):
    monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)
    provider = AlphaVantageProvider(api_key="")
    with pytest.raises(ProviderError):
        provider.fetch_historical("AAPL")


def test_alpha_vantage_provider_rejects_non_daily_interval(monkeypatch):
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "test-key")
    provider = AlphaVantageProvider()
    with pytest.raises(ProviderError):
        provider.fetch_historical("AAPL", interval="1h")


def test_alpha_vantage_provider_raises_on_out_of_range_request(monkeypatch):
    payload = _sample_payload()

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "test-key")
    monkeypatch.setattr("src.data.providers.urlopen", lambda url, timeout: _Resp())

    provider = AlphaVantageProvider()
    with pytest.raises(ProviderError):
        provider.fetch_historical("AAPL", start="2023-01-01", end="2023-01-10")
