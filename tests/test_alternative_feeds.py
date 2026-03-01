"""Tests for alternative data provider contract and registry (Step 99)."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from config.settings import Settings
from src.data.alternative_feeds import (
    AlternativeDataRegistry,
    BaseAlternativeDataProvider,
    WeatherDataProvider,
    register_configured_providers,
)
from src.data.models import Bar
from src.strategies.base import BaseStrategy


class _DummyAltProvider(BaseAlternativeDataProvider):
    def __init__(self) -> None:
        self.calls = 0

    @property
    def provider_name(self) -> str:
        return "dummy_alt"

    def fetch(self, symbol: str, start=None, end=None, **params) -> pd.DataFrame:
        _ = (symbol, start, end, params)
        self.calls += 1
        return pd.DataFrame(
            {
                "macro_feature": [1.0, 2.0, 3.0],
            },
            index=pd.DatetimeIndex(
                [
                    "2024-01-01T00:00:00Z",
                    "2024-01-02T00:00:00Z",
                    "2024-01-03T00:00:00Z",
                ]
            ),
        )

    def feature_columns(self) -> list[str]:
        return ["macro_feature"]


class _NoopStrategy(BaseStrategy):
    def generate_signal(self, symbol: str):
        _ = symbol
        return None


def test_registry_registers_provider_and_lists_names() -> None:
    registry = AlternativeDataRegistry()
    provider = _DummyAltProvider()

    registry.register_provider(provider)

    assert registry.list_providers() == ["dummy_alt"]


def test_registry_uses_left_join_and_preserves_bar_index() -> None:
    registry = AlternativeDataRegistry()
    provider = _DummyAltProvider()
    registry.register_provider(provider)

    base_index = pd.DatetimeIndex(
        [
            "2024-01-01T00:00:00Z",
            "2024-01-02T00:00:00Z",
            "2024-01-05T00:00:00Z",
        ]
    )

    merged = registry.get_features("AAPL", base_index)

    assert list(merged.index) == list(pd.to_datetime(base_index, utc=True))
    assert "macro_feature" in merged.columns
    assert merged.loc[pd.Timestamp("2024-01-01T00:00:00Z"), "macro_feature"] == 1.0
    assert pd.isna(merged.loc[pd.Timestamp("2024-01-05T00:00:00Z"), "macro_feature"])


def test_registry_as_of_prevents_lookahead_rows() -> None:
    registry = AlternativeDataRegistry()
    provider = _DummyAltProvider()
    registry.register_provider(provider)

    base_index = pd.DatetimeIndex(
        [
            "2024-01-01T00:00:00Z",
            "2024-01-02T00:00:00Z",
            "2024-01-03T00:00:00Z",
        ]
    )

    merged = registry.get_features(
        "AAPL",
        base_index,
        as_of=datetime(2024, 1, 2, tzinfo=timezone.utc),
    )

    assert merged.loc[pd.Timestamp("2024-01-01T00:00:00Z"), "macro_feature"] == 1.0
    assert merged.loc[pd.Timestamp("2024-01-02T00:00:00Z"), "macro_feature"] == 2.0
    assert pd.isna(merged.loc[pd.Timestamp("2024-01-03T00:00:00Z"), "macro_feature"])


def test_strategy_accessor_returns_empty_when_registry_unset() -> None:
    strategy = _NoopStrategy(Settings())

    strategy.on_bar(
        Bar(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            open=1.0,
            high=1.0,
            low=1.0,
            close=1.0,
            volume=1.0,
        )
    )
    alt = strategy.get_alternative_features("AAPL")

    assert alt.empty


def test_strategy_accessor_reads_from_registry() -> None:
    strategy = _NoopStrategy(Settings())
    registry = AlternativeDataRegistry()
    provider = _DummyAltProvider()
    registry.register_provider(provider)
    strategy.set_alternative_registry(registry)

    strategy.on_bar(
        Bar(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            open=1.0,
            high=1.0,
            low=1.0,
            close=1.0,
            volume=1.0,
        )
    )
    strategy.on_bar(
        Bar(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 2, tzinfo=timezone.utc),
            open=1.0,
            high=1.0,
            low=1.0,
            close=1.0,
            volume=1.0,
        )
    )

    alt = strategy.get_alternative_features("AAPL")

    assert "macro_feature" in alt.columns
    assert provider.calls == 1


def test_weather_provider_fetches_and_resamples_daily(monkeypatch) -> None:
    class _DummyResponse:
        def __init__(self, payload: str) -> None:
            self._payload = payload.encode("utf-8")

        def read(self):
            return self._payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            _ = (exc_type, exc, tb)
            return False

    payload = """{
      "hourly": {
        "time": ["2024-01-01T00:00", "2024-01-01T12:00", "2024-01-02T00:00"],
        "temperature_2m": [10.0, 14.0, 11.0],
        "relative_humidity_2m": [80.0, 70.0, 75.0]
      }
    }"""

    monkeypatch.setattr(
        "src.data.alternative_feeds.urlopen",
        lambda *args, **kwargs: _DummyResponse(payload),
    )

    provider = WeatherDataProvider(
        symbol_locations={"DEFAULT": {"latitude": 51.5, "longitude": -0.1}},
    )
    frame = provider.fetch(
        "HSBA.L",
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 1, 2, tzinfo=timezone.utc),
    )

    assert "weather_temperature_2m" in frame.columns
    assert "weather_relative_humidity_2m" in frame.columns
    assert frame.loc[pd.Timestamp("2024-01-01", tz="UTC"), "weather_temperature_2m"] == 12.0


def test_weather_provider_forward_fill_limit(monkeypatch) -> None:
    class _DummyResponse:
        def __init__(self, payload: str) -> None:
            self._payload = payload.encode("utf-8")

        def read(self):
            return self._payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            _ = (exc_type, exc, tb)
            return False

    payload = """{
      "hourly": {
        "time": ["2024-01-01T00:00"],
        "temperature_2m": [10.0],
        "relative_humidity_2m": [80.0]
      }
    }"""
    monkeypatch.setattr(
        "src.data.alternative_feeds.urlopen",
        lambda *args, **kwargs: _DummyResponse(payload),
    )

    provider = WeatherDataProvider(
        symbol_locations={"DEFAULT": {"latitude": 51.5, "longitude": -0.1}},
        max_ffill_bars=1,
    )
    frame = provider.fetch(
        "HSBA.L",
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 1, 4, tzinfo=timezone.utc),
    )

    assert frame.loc[pd.Timestamp("2024-01-01", tz="UTC"), "weather_temperature_2m"] == 10.0


def test_register_configured_providers_adds_weather_provider() -> None:
    settings = Settings()
    settings.alternative_data.enabled = True
    settings.alternative_data.providers = ["weather"]
    settings.alternative_data.provider_enabled = {"weather": True}

    registry = AlternativeDataRegistry()
    register_configured_providers(registry, settings)

    assert "weather" in registry.list_providers()
