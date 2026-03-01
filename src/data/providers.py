"""Market data provider adapters and factory helpers."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


class ProviderError(RuntimeError):
    """Raised when a market-data provider request fails."""


class HistoricalDataProvider(Protocol):
    """Provider contract for historical OHLCV retrieval."""

    def fetch_historical(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame: ...


@dataclass
class YFinanceProvider:
    """Default free data provider using yfinance."""

    retry_enabled: bool = True
    period_max_attempts: int = 1
    period_backoff_base_seconds: float = 0.0
    period_backoff_max_seconds: float = 0.0
    start_end_max_attempts: int = 1
    start_end_backoff_base_seconds: float = 0.0
    start_end_backoff_max_seconds: float = 0.0

    @staticmethod
    def _request_type(start: str | None) -> str:
        return "start_end" if start else "period"

    def _retry_policy(self, request_type: str) -> tuple[int, float, float]:
        if not self.retry_enabled:
            return 1, 0.0, 0.0
        if request_type == "start_end":
            max_attempts = max(1, self.start_end_max_attempts)
            return (
                max_attempts,
                max(0.0, self.start_end_backoff_base_seconds),
                max(0.0, self.start_end_backoff_max_seconds),
            )
        max_attempts = max(1, self.period_max_attempts)
        return (
            max_attempts,
            max(0.0, self.period_backoff_base_seconds),
            max(0.0, self.period_backoff_max_seconds),
        )

    @staticmethod
    def _retry_delay(attempt: int, base_seconds: float, max_seconds: float) -> float:
        if base_seconds <= 0.0:
            return 0.0
        delay = base_seconds * (2 ** (attempt - 1))
        if max_seconds > 0.0:
            return min(delay, max_seconds)
        return delay

    def fetch_historical(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        ticker = yf.Ticker(symbol)
        request_type = self._request_type(start)
        max_attempts, base_backoff_seconds, max_backoff_seconds = self._retry_policy(request_type)

        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                if start:
                    result = ticker.history(
                        start=start, end=end, interval=interval, auto_adjust=True
                    )
                else:
                    result = ticker.history(period=period, interval=interval, auto_adjust=True)

                if result.empty:
                    if attempt >= max_attempts:
                        logger.warning(
                            "YFinance retries exhausted (empty result) for %s interval=%s request_type=%s attempts=%s",
                            symbol,
                            interval,
                            request_type,
                            attempt,
                        )
                        return result
                    delay = self._retry_delay(attempt, base_backoff_seconds, max_backoff_seconds)
                    logger.warning(
                        "YFinance empty result for %s interval=%s request_type=%s attempt=%s/%s; retrying in %.2fs",
                        symbol,
                        interval,
                        request_type,
                        attempt,
                        max_attempts,
                        delay,
                    )
                    if delay > 0.0:
                        time.sleep(delay)
                    continue

                return result
            except Exception as exc:  # pylint: disable=broad-except
                last_error = exc
                if attempt >= max_attempts:
                    logger.warning(
                        "YFinance retries exhausted (exception) for %s interval=%s request_type=%s attempts=%s error=%s",
                        symbol,
                        interval,
                        request_type,
                        attempt,
                        exc,
                    )
                    raise
                delay = self._retry_delay(attempt, base_backoff_seconds, max_backoff_seconds)
                logger.warning(
                    "YFinance request failed for %s interval=%s request_type=%s attempt=%s/%s; retrying in %.2fs (%s)",
                    symbol,
                    interval,
                    request_type,
                    attempt,
                    max_attempts,
                    delay,
                    exc,
                )
                if delay > 0.0:
                    time.sleep(delay)

        if last_error is not None:
            raise last_error

        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])


@dataclass
class NotImplementedProvider:
    """Scaffold adapter for providers not yet wired in this codebase."""

    name: str

    def fetch_historical(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        raise NotImplementedError(
            f"Provider '{self.name}' adapter is not implemented yet for symbol '{symbol}'"
        )


@dataclass
class PolygonProvider:
    """Polygon.io historical aggregate bars provider."""

    api_key: str | None = None
    base_url: str = "https://api.polygon.io"

    def _resolve_api_key(self) -> str:
        key = (self.api_key or os.getenv("POLYGON_API_KEY", "")).strip()
        if not key:
            raise ProviderError("POLYGON_API_KEY is required for PolygonProvider")
        return key

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        clean = (symbol or "").strip().upper()
        if not clean:
            raise ProviderError("Polygon symbol cannot be empty")
        if clean.endswith(".L"):
            return clean
        return clean

    @staticmethod
    def _resolve_dates(
        period: str,
        start: str | None,
        end: str | None,
    ) -> tuple[str, str]:
        if start:
            end_value = end or datetime.now(timezone.utc).strftime("%Y-%m-%d")
            return start, end_value

        now = datetime.now(timezone.utc).date()
        mapping = {
            "1d": 1,
            "5d": 5,
            "1mo": 30,
            "3mo": 90,
            "6mo": 180,
            "1y": 365,
            "2y": 730,
            "5y": 1825,
            "10y": 3650,
            "max": 3650,
        }
        lookback_days = mapping.get(period, 365)
        start_date = now - timedelta(days=lookback_days)
        return start_date.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")

    @staticmethod
    def _resolve_interval(interval: str) -> tuple[int, str]:
        value = (interval or "1d").strip().lower()
        if value.endswith("m"):
            return int(value[:-1]), "minute"
        if value.endswith("h"):
            return int(value[:-1]), "hour"
        if value.endswith("d"):
            return int(value[:-1]), "day"
        raise ProviderError(f"Unsupported interval for PolygonProvider: {interval}")

    def fetch_historical(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        api_key = self._resolve_api_key()
        ticker = self._normalize_symbol(symbol)
        from_date, to_date = self._resolve_dates(period, start, end)
        multiplier, timespan = self._resolve_interval(interval)

        path = f"/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_date}/{to_date}"
        query = urlencode(
            {
                "adjusted": "true",
                "sort": "asc",
                "limit": 50000,
                "apiKey": api_key,
            }
        )
        url = f"{self.base_url}{path}?{query}"

        try:
            with urlopen(url, timeout=20) as response:  # noqa: S310
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 429:
                raise ProviderError("Polygon rate limit exceeded") from exc
            raise ProviderError(f"Polygon request failed ({exc.code})") from exc
        except URLError as exc:
            raise ProviderError(f"Polygon network error: {exc.reason}") from exc

        if payload.get("status") == "ERROR":
            message = str(payload.get("error") or "Polygon returned an error")
            if "rate" in message.lower() and "limit" in message.lower():
                raise ProviderError("Polygon rate limit exceeded")
            raise ProviderError(message)

        results = payload.get("results") or []
        if not results:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        frame = pd.DataFrame(results)
        frame = frame.rename(
            columns={
                "o": "open",
                "h": "high",
                "l": "low",
                "c": "close",
                "v": "volume",
                "t": "timestamp_ms",
            }
        )
        frame["timestamp"] = pd.to_datetime(frame["timestamp_ms"], unit="ms", utc=True)
        frame = frame.set_index("timestamp")

        return frame[["open", "high", "low", "close", "volume"]].astype(float)


@dataclass
class AlphaVantageProvider:
    """Alpha Vantage daily time series provider (free tier)."""

    api_key: str | None = None
    base_url: str = "https://www.alphavantage.co/query"
    max_retries: int = 3
    backoff_base_seconds: float = 1.0

    def _resolve_api_key(self) -> str:
        key = (self.api_key or os.getenv("ALPHA_VANTAGE_API_KEY", "")).strip()
        if not key:
            raise ProviderError("ALPHA_VANTAGE_API_KEY is required for AlphaVantageProvider")
        return key

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        clean = (symbol or "").strip().upper()
        if not clean:
            raise ProviderError("Alpha Vantage symbol cannot be empty")
        if clean.endswith(".L"):
            clean = clean.replace(".L", ".LON")
        return clean

    def _request(self, params: dict) -> dict:
        url = f"{self.base_url}?{urlencode(params)}"
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                with urlopen(url, timeout=20) as response:  # noqa: S310
                    payload = json.loads(response.read().decode("utf-8"))
                return payload
            except HTTPError as exc:
                last_error = exc
                if exc.code in {429, 503} and attempt < self.max_retries - 1:
                    time.sleep(self.backoff_base_seconds * (2**attempt))
                    continue
                raise ProviderError(f"Alpha Vantage request failed ({exc.code})") from exc
            except URLError as exc:
                last_error = exc
                raise ProviderError(f"Alpha Vantage network error: {exc.reason}") from exc
            except json.JSONDecodeError as exc:
                last_error = exc
                raise ProviderError("Alpha Vantage returned invalid JSON") from exc

        raise ProviderError("Alpha Vantage request failed") from last_error

    @staticmethod
    def _parse_time_series(payload: dict) -> pd.DataFrame:
        if "Error Message" in payload:
            raise ProviderError(str(payload["Error Message"]))
        if "Note" in payload:
            raise ProviderError("Alpha Vantage rate limit exceeded")
        if "Information" in payload:
            raise ProviderError(str(payload["Information"]))

        series = payload.get("Time Series (Daily)")
        if not series:
            raise ProviderError("Alpha Vantage response missing time series")

        frame = pd.DataFrame.from_dict(series, orient="index")
        frame.index = pd.to_datetime(frame.index, utc=True)
        frame = frame.rename(
            columns={
                "1. open": "open",
                "2. high": "high",
                "3. low": "low",
                "4. close": "close",
                "5. volume": "volume",
            }
        )
        return frame[["open", "high", "low", "close", "volume"]].astype(float)

    def fetch_historical(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        if interval and interval != "1d":
            raise ProviderError("Alpha Vantage free tier supports daily bars only")

        api_key = self._resolve_api_key()
        ticker = self._normalize_symbol(symbol)
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": ticker,
            "apikey": api_key,
            "outputsize": "compact",
        }
        payload = self._request(params)
        frame = self._parse_time_series(payload)

        start_ts = None
        if start:
            start_ts = pd.to_datetime(start, utc=True)
            frame = frame[frame.index >= start_ts]
        if end:
            end_ts = pd.to_datetime(end, utc=True)
            frame = frame[frame.index <= end_ts]

        if start_ts is not None:
            if frame.empty:
                logger.warning("Alpha Vantage returned no data for %s; falling back", ticker)
                raise ProviderError(
                    "Alpha Vantage compact coverage insufficient for requested range"
                )
            oldest = frame.index.min()
            if oldest > start_ts:
                logger.warning("Alpha Vantage data too recent for %s; falling back", ticker)
                raise ProviderError(
                    "Alpha Vantage data too recent for requested range; falling back"
                )

        return frame.sort_index()


def get_provider(
    name: str,
    yfinance_provider: YFinanceProvider | None = None,
) -> HistoricalDataProvider:
    """Factory for known providers.

    Implemented: yfinance, polygon
    Implemented: yfinance, polygon, alpha_vantage
    Scaffolded: alpaca
    """
    normalized = (name or "yfinance").strip().lower()
    if normalized in {"yfinance", "yf", "yahoo"}:
        return yfinance_provider or YFinanceProvider()
    if normalized in {"polygon"}:
        return PolygonProvider()
    if normalized in {"alpha_vantage"}:
        return AlphaVantageProvider()
    if normalized in {"alpaca"}:
        return NotImplementedProvider(normalized)

    logger.warning("Unknown data provider '%s'; defaulting to yfinance", name)
    return YFinanceProvider()
