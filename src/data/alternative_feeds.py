"""Alternative data provider contract and registry.

Provides a pluggable contract for non-OHLCV feature sources and a registry
that merges provider outputs onto bar timestamps without lookahead.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from typing import Any, Optional

import pandas as pd


class BaseAlternativeDataProvider(ABC):
    """Abstract contract for alternative feature providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique provider identifier."""

    @abstractmethod
    def fetch(
        self,
        symbol: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        **params: Any,
    ) -> pd.DataFrame:
        """Fetch provider data for a symbol.

        Returns a DataFrame indexed by UTC-aware timestamps.
        """

    @abstractmethod
    def feature_columns(self) -> list[str]:
        """Return provider feature columns exposed by `fetch()`."""


class AlternativeDataRegistry:
    """Registry and merge engine for alternative data providers."""

    def __init__(self) -> None:
        self._providers: dict[str, BaseAlternativeDataProvider] = {}
        self._cache: dict[tuple, pd.DataFrame] = {}

    def register_provider(self, provider: BaseAlternativeDataProvider) -> None:
        """Register a provider by `provider_name`."""
        self._providers[provider.provider_name] = provider

    def list_providers(self) -> list[str]:
        """List registered provider names."""
        return sorted(self._providers.keys())

    def clear_cache(self) -> None:
        """Clear in-memory fetch cache."""
        self._cache.clear()

    def prefetch(
        self,
        symbol: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> None:
        """Warm provider cache for a symbol/date range."""
        for provider_name in self.list_providers():
            self._get_provider_frame(provider_name, symbol, start, end)

    def get_features(
        self,
        symbol: str,
        base_index: pd.DatetimeIndex,
        *,
        as_of: Optional[datetime] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Return provider features merged on `base_index` timestamps.

        Merge policy:
        - left-join to preserve bar index cardinality
        - sort by timestamp ascending
        - trim provider rows to `as_of` to prevent lookahead
        """
        if base_index.empty or not self._providers:
            return pd.DataFrame(index=base_index)

        normalized_index = pd.to_datetime(base_index, utc=True)
        merged = pd.DataFrame(index=normalized_index)

        for provider_name in self.list_providers():
            provider_frame = self._get_provider_frame(provider_name, symbol, start, end)
            if provider_frame.empty:
                continue

            provider_index = pd.to_datetime(provider_frame.index, utc=True)
            provider_frame = provider_frame.copy()
            provider_frame.index = provider_index
            if as_of is not None:
                cutoff = pd.to_datetime(as_of, utc=True)
                provider_frame = provider_frame.loc[provider_frame.index <= cutoff]

            if provider_frame.empty:
                continue

            provider_frame = provider_frame.sort_index()
            merged = merged.join(provider_frame, how="left")

        return merged

    def _get_provider_frame(
        self,
        provider_name: str,
        symbol: str,
        start: Optional[datetime],
        end: Optional[datetime],
    ) -> pd.DataFrame:
        cache_key = (
            provider_name,
            symbol,
            pd.to_datetime(start, utc=True) if start is not None else None,
            pd.to_datetime(end, utc=True) if end is not None else None,
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        provider = self._providers[provider_name]
        frame = provider.fetch(symbol, start=start, end=end)
        if frame is None:
            frame = pd.DataFrame()
        if not frame.empty:
            frame = frame.copy()
            frame.index = pd.to_datetime(frame.index, utc=True)
        self._cache[cache_key] = frame
        return frame


class WeatherDataProvider(BaseAlternativeDataProvider):
    """Open-Meteo weather feature provider (no API key required)."""

    def __init__(
        self,
        symbol_locations: Optional[dict[str, dict[str, float]]] = None,
        *,
        max_ffill_bars: int = 3,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._symbol_locations = symbol_locations or {}
        self._max_ffill_bars = max(0, int(max_ffill_bars))
        self._timeout_seconds = timeout_seconds

    @property
    def provider_name(self) -> str:
        return "weather"

    def fetch(
        self,
        symbol: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        **params: Any,
    ) -> pd.DataFrame:
        location = self._symbol_locations.get(symbol) or self._symbol_locations.get("DEFAULT")
        if not location:
            return pd.DataFrame(columns=self.feature_columns())

        if start is None or end is None:
            return pd.DataFrame(columns=self.feature_columns())

        start_dt = pd.to_datetime(start, utc=True)
        end_dt = pd.to_datetime(end, utc=True)
        if end_dt < start_dt:
            return pd.DataFrame(columns=self.feature_columns())

        query = {
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
            "hourly": "temperature_2m,relative_humidity_2m",
            "start_date": start_dt.date().isoformat(),
            "end_date": end_dt.date().isoformat(),
            "timezone": "UTC",
        }
        url = f"https://archive-api.open-meteo.com/v1/archive?{urlencode(query)}"
        request = Request(url, headers={"Accept": "application/json"})
        with urlopen(request, timeout=self._timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))

        hourly = payload.get("hourly") or {}
        timestamps = hourly.get("time") or []
        if not timestamps:
            return pd.DataFrame(columns=self.feature_columns())

        frame = pd.DataFrame(
            {
                "weather_temperature_2m": hourly.get("temperature_2m") or [],
                "weather_relative_humidity_2m": hourly.get("relative_humidity_2m") or [],
            },
            index=pd.to_datetime(timestamps, utc=True),
        )
        frame = frame.sort_index()
        frame = frame.resample("1D").mean()
        if self._max_ffill_bars > 0:
            frame = frame.ffill(limit=self._max_ffill_bars)
        return frame

    def feature_columns(self) -> list[str]:
        return ["weather_temperature_2m", "weather_relative_humidity_2m"]


def register_configured_providers(
    registry: AlternativeDataRegistry,
    settings: Any,
) -> None:
    """Register configured alternative data providers from settings."""
    config = getattr(settings, "alternative_data", None)
    if config is None or not getattr(config, "enabled", False):
        return

    providers = list(getattr(config, "providers", []) or [])
    provider_enabled = dict(getattr(config, "provider_enabled", {}) or {})

    for provider_name in providers:
        enabled = provider_enabled.get(provider_name, True)
        if not enabled:
            continue
        normalized = str(provider_name).strip().lower()
        if normalized == "weather":
            registry.register_provider(
                WeatherDataProvider(
                    symbol_locations=getattr(config, "weather_symbol_locations", {}),
                    max_ffill_bars=getattr(config, "max_ffill_bars", 3),
                )
            )
