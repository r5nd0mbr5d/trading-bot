"""Market data feed.

Default source: yfinance (free, no API key, covers US equities + ETFs).
For production upgrade to: Massive (Polygon.io) or Alpaca data API.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from config.settings import Settings
from src.data.market_data_store import MarketDataStore
from src.data.models import Bar
from src.data.providers import HistoricalDataProvider, get_provider
from src.data.symbol_utils import normalize_symbol

logger = logging.getLogger(__name__)


class MassiveWebSocketFeed:
    """Polygon (Massive) WebSocket feed for minute aggregate bars."""

    def __init__(
        self,
        api_key: str | None = None,
        url: str = "wss://socket.polygon.io/stocks",
        max_retries: int = 5,
        backoff_base_seconds: float = 2.0,
        backoff_max_seconds: float = 30.0,
    ) -> None:
        self._api_key = api_key or os.getenv("POLYGON_API_KEY", "")
        self._url = url
        self._max_retries = max_retries
        self._backoff_base_seconds = backoff_base_seconds
        self._backoff_max_seconds = backoff_max_seconds

    async def stream(
        self,
        symbols: List[str],
        callback: Callable[[Bar], None],
        *,
        heartbeat_callback: Optional[Callable[[dict[str, Any]], None]] = None,
        error_callback: Optional[Callable[[dict[str, Any]], None]] = None,
        max_messages: Optional[int] = None,
    ) -> None:
        if not self._api_key:
            raise RuntimeError("POLYGON_API_KEY is required for MassiveWebSocketFeed")

        try:
            import websockets
        except ImportError as exc:
            raise RuntimeError("websockets is required for MassiveWebSocketFeed") from exc

        symbols = [s.strip().upper() for s in symbols if s and s.strip()]
        if not symbols:
            raise RuntimeError("No symbols provided for MassiveWebSocketFeed")

        for attempts in range(1, self._max_retries + 1):
            try:
                async with websockets.connect(self._url, ping_interval=20, ping_timeout=20) as ws:
                    await ws.send(json.dumps({"action": "auth", "params": self._api_key}))
                    subscribe = ",".join([f"AM.{symbol}" for symbol in symbols])
                    await ws.send(json.dumps({"action": "subscribe", "params": subscribe}))

                    bar_count = 0
                    while True:
                        raw = await ws.recv()
                        try:
                            messages = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        if isinstance(messages, dict):
                            messages = [messages]

                        bars_processed = 0
                        for event in messages:
                            if event.get("ev") != "AM":
                                continue
                            symbol = event.get("sym")
                            if symbol not in symbols:
                                continue

                            timestamp_ms = event.get("s") or event.get("t")
                            if timestamp_ms is None:
                                continue

                            ts = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
                            bar = Bar(
                                symbol=symbol,
                                timestamp=ts,
                                open=float(event.get("o", 0.0)),
                                high=float(event.get("h", 0.0)),
                                low=float(event.get("l", 0.0)),
                                close=float(event.get("c", 0.0)),
                                volume=float(event.get("v", 0.0)),
                            )
                            callback(bar)
                            bars_processed += 1
                            bar_count += 1

                        if bars_processed and heartbeat_callback is not None:
                            heartbeat_callback(
                                {
                                    "event": "STREAM_HEARTBEAT",
                                    "bars_processed": bars_processed,
                                    "symbol_count": len(symbols),
                                }
                            )

                        if max_messages is not None and bar_count >= max_messages:
                            return
            except Exception as exc:
                if error_callback is not None:
                    error_callback(
                        {
                            "event": "STREAM_WEBSOCKET_ERROR",
                            "attempt": attempts,
                            "max_attempts": self._max_retries,
                            "error": str(exc),
                        }
                    )
                if attempts >= self._max_retries:
                    raise RuntimeError("websocket_failure_limit_reached") from exc
                delay = min(
                    self._backoff_max_seconds,
                    self._backoff_base_seconds * (2 ** (attempts - 1)),
                )
                await asyncio.sleep(delay)


class MarketDataFeed:
    """Fetches historical OHLCV data and provides a simulated streaming feed."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._cache: Dict[str, pd.DataFrame] = {}
        self._primary_provider: HistoricalDataProvider = get_provider(settings.data.source)
        fallback_sources = getattr(settings.data, "fallback_sources", []) or []
        self._fallback_providers: List[HistoricalDataProvider] = [
            get_provider(source) for source in fallback_sources
        ]
        self._cache_store: Optional[MarketDataStore] = None
        if getattr(settings.data, "cache_enabled", False):
            self._cache_store = MarketDataStore(settings.data.cache_dir)

    @staticmethod
    def _normalize_ohlcv_index(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Normalize provider frame columns/index to project OHLCV contract."""
        if df.empty:
            return df

        normalized = df.copy()
        normalized.columns = [str(c).lower() for c in normalized.columns]

        dt_index = pd.to_datetime(normalized.index)
        if dt_index.tz is None:
            logger.warning("Provider returned naive timestamps for %s; localizing to UTC", symbol)
            dt_index = dt_index.tz_localize(timezone.utc)
        else:
            dt_index = dt_index.tz_convert(timezone.utc)
        normalized.index = dt_index
        return normalized

    def _fetch_with_fallbacks(
        self,
        symbol: str,
        period: str,
        interval: str,
        start: str = None,
        end: str = None,
    ) -> pd.DataFrame:
        fallback_sources = getattr(self.settings.data, "fallback_sources", []) or []
        providers: List[tuple[str, str, HistoricalDataProvider]] = [
            (self.settings.data.source, self.settings.data.source, self._primary_provider),
            *[
                (f"fallback:{index+1}", str(source), provider)
                for index, (source, provider) in enumerate(
                    zip(fallback_sources, self._fallback_providers)
                )
            ],
        ]

        last_error: Exception | None = None
        for provider_label, provider_source, provider in providers:
            try:
                symbol_for_provider = symbol
                if provider_source.strip().lower() == "yfinance":
                    symbol_for_provider = normalize_symbol(symbol, "yfinance")
                df = provider.fetch_historical(
                    symbol=symbol_for_provider,
                    period=period,
                    interval=interval,
                    start=start,
                    end=end,
                )
                if df.empty:
                    raise ValueError(f"Empty dataset from provider '{provider_label}'")
                if provider is not self._primary_provider:
                    logger.warning(
                        "Primary data provider failed; using %s for %s",
                        provider_label,
                        symbol,
                    )
                return df
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Data provider '%s' failed for %s: %s",
                    provider_label,
                    symbol,
                    exc,
                )

        raise ValueError(
            f"No data returned for {symbol}. Check provider availability and date range."
        ) from last_error

    def fetch_historical(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
        start: str = None,
        end: str = None,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data from Yahoo Finance (free, no key required).

        Prefer start/end for backtesting; period for recent/streaming data.

        Args:
            symbol:   Ticker e.g. 'AAPL'
            period:   yfinance period string — used only when start is None
            interval: bar size e.g. '1d', '1h', '5m'
            start:    ISO date '2022-01-01' — overrides period when set
            end:      ISO date '2024-01-01'
        """
        cache_key = f"{symbol}:{start or period}:{end or ''}:{interval}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        cache_store = self._cache_store
        range_start, range_end = self._resolve_range(start, end, period)
        if cache_store is not None and range_start is not None and range_end is not None:
            missing = cache_store.missing_ranges(symbol, interval, range_start, range_end)
            if missing:
                for missing_start, missing_end in missing:
                    raw_df = self._fetch_with_fallbacks(
                        symbol=symbol,
                        period=period,
                        interval=interval,
                        start=missing_start.date().isoformat(),
                        end=missing_end.date().isoformat(),
                    )
                    df = self._normalize_ohlcv_index(raw_df, symbol)
                    cache_store.put(symbol, interval, df, self.settings.data.source)
            cached_df = cache_store.get(symbol, interval, range_start, range_end)
            if cached_df is not None and not cached_df.empty:
                self._cache[cache_key] = cached_df
                return cached_df

        logger.info(
            "Fetching %s (%s, %s)",
            symbol,
            interval,
            f"{start} -> {end or 'today'}" if start else f"period={period}",
        )
        raw_df = self._fetch_with_fallbacks(
            symbol=symbol,
            period=period,
            interval=interval,
            start=start,
            end=end,
        )
        df = self._normalize_ohlcv_index(raw_df, symbol)
        if cache_store is not None and range_start is not None and range_end is not None:
            cache_store.put(symbol, interval, df, self.settings.data.source)
        self._cache[cache_key] = df
        return df

    @staticmethod
    def _resolve_range(
        start: Optional[str],
        end: Optional[str],
        period: Optional[str],
    ) -> tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
        if start:
            start_ts = pd.to_datetime(start, utc=True, errors="coerce")
        else:
            start_ts = None

        if end:
            end_ts = pd.to_datetime(end, utc=True, errors="coerce")
        else:
            end_ts = None

        if start_ts is None and period:
            delta = MarketDataFeed._period_to_timedelta(period)
            if delta is not None:
                end_ts = end_ts or pd.Timestamp(datetime.now(timezone.utc))
                start_ts = end_ts - delta

        if start_ts is None or end_ts is None:
            return None, None
        return start_ts, end_ts

    @staticmethod
    def _period_to_timedelta(period: str) -> Optional[pd.Timedelta]:
        if not period:
            return None
        unit = period[-1]
        try:
            value = int(period[:-1])
        except ValueError:
            return None
        if unit == "d":
            return pd.Timedelta(days=value)
        if unit == "w":
            return pd.Timedelta(weeks=value)
        if unit == "m":
            return pd.Timedelta(days=value * 30)
        if unit == "y":
            return pd.Timedelta(days=value * 365)
        return None

    def fetch_multi(
        self,
        symbols: List[str],
        period: str = "1y",
        interval: str = "1d",
    ) -> Dict[str, pd.DataFrame]:
        """Fetch multiple symbols. yfinance batches the HTTP requests internally."""
        return {s: self.fetch_historical(s, period, interval) for s in symbols}

    def to_bars(self, symbol: str, df: pd.DataFrame) -> List[Bar]:
        """Convert a DataFrame row-by-row into Bar objects."""
        bars = []
        for ts, row in df.iterrows():
            dt = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            bars.append(
                Bar(
                    symbol=symbol,
                    timestamp=dt,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume", 0)),
                )
            )
        return bars

    async def stream(
        self,
        symbols: List[str],
        callback: Callable[[Bar], None],
        interval_seconds: int = 300,
        *,
        heartbeat_callback: Optional[Callable[[dict[str, Any]], None]] = None,
        error_callback: Optional[Callable[[dict[str, Any]], None]] = None,
        backoff_base_seconds: float = 0.25,
        backoff_max_seconds: float = 5.0,
        max_consecutive_failure_cycles: Optional[int] = None,
        max_cycles: Optional[int] = None,
    ):
        """
        Simulated real-time stream using polling.

        For production: replace with Alpaca WebSocket stream or Polygon.io feed.
        Alpaca example: https://docs.alpaca.markets/reference/streaming
        """
        if self.settings.data.source == "polygon" and self.settings.broker.provider == "ibkr":
            ws_feed = MassiveWebSocketFeed()
            await ws_feed.stream(
                symbols,
                callback,
                heartbeat_callback=heartbeat_callback,
                error_callback=error_callback,
                max_messages=max_cycles,
            )
            return
        logger.info(f"Stream started for {symbols} (poll every {interval_seconds}s)")
        consecutive_failure_cycles = 0
        cycle_count = 0

        while True:
            cycle_count += 1
            cycle_errors = 0
            bars_processed = 0

            for symbol in symbols:
                try:
                    df = self.fetch_historical(symbol, period="5d", interval="1m")
                    self._cache.pop(f"{symbol}:5d:1m", None)  # don't cache stream data
                    if not df.empty:
                        row = df.iloc[-1]
                        dt = df.index[-1]
                        dt_obj = dt.to_pydatetime() if hasattr(dt, "to_pydatetime") else dt
                        if dt_obj.tzinfo is None:
                            dt_obj = dt_obj.replace(tzinfo=timezone.utc)
                        else:
                            dt_obj = dt_obj.astimezone(timezone.utc)
                        bar = Bar(
                            symbol=symbol,
                            timestamp=dt_obj,
                            open=float(row["open"]),
                            high=float(row["high"]),
                            low=float(row["low"]),
                            close=float(row["close"]),
                            volume=float(row.get("volume", 0)),
                        )
                        callback(bar)
                        bars_processed += 1
                except Exception as e:
                    logger.error(f"Stream error for {symbol}: {e}")
                    cycle_errors += 1
                    if error_callback is not None:
                        error_callback(
                            {
                                "event": "STREAM_SYMBOL_ERROR",
                                "symbol": symbol,
                                "error": str(e),
                                "cycle": cycle_count,
                            }
                        )

            if bars_processed > 0:
                if consecutive_failure_cycles > 0 and heartbeat_callback is not None:
                    heartbeat_callback(
                        {
                            "event": "STREAM_RECOVERED",
                            "cycle": cycle_count,
                            "bars_processed": bars_processed,
                            "prior_failure_cycles": consecutive_failure_cycles,
                        }
                    )
                consecutive_failure_cycles = 0
                if heartbeat_callback is not None:
                    heartbeat_callback(
                        {
                            "event": "STREAM_HEARTBEAT",
                            "cycle": cycle_count,
                            "bars_processed": bars_processed,
                            "symbol_count": len(symbols),
                        }
                    )
                sleep_seconds = max(interval_seconds, 0)
            else:
                consecutive_failure_cycles += 1
                backoff_delay = min(
                    max(backoff_base_seconds, 0.0) * (2 ** (consecutive_failure_cycles - 1)),
                    max(backoff_max_seconds, 0.0),
                )
                sleep_seconds = backoff_delay
                if error_callback is not None:
                    error_callback(
                        {
                            "event": "STREAM_BACKOFF",
                            "cycle": cycle_count,
                            "errors": cycle_errors,
                            "consecutive_failure_cycles": consecutive_failure_cycles,
                            "backoff_seconds": backoff_delay,
                        }
                    )
                if (
                    max_consecutive_failure_cycles is not None
                    and consecutive_failure_cycles >= max_consecutive_failure_cycles
                ):
                    if error_callback is not None:
                        error_callback(
                            {
                                "event": "STREAM_FAILURE_LIMIT_REACHED",
                                "cycle": cycle_count,
                                "consecutive_failure_cycles": consecutive_failure_cycles,
                                "max_consecutive_failure_cycles": max_consecutive_failure_cycles,
                            }
                        )
                    raise RuntimeError(
                        "stream_failure_limit_reached: "
                        f"{consecutive_failure_cycles} >= {max_consecutive_failure_cycles}"
                    )

            if max_cycles is not None and cycle_count >= max_cycles:
                return

            await asyncio.sleep(sleep_seconds)
