"""Persistent market data cache backed by SQLite and Parquet."""

from __future__ import annotations

import importlib.util
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CacheRange:
    start: pd.Timestamp
    end: pd.Timestamp


class MarketDataStore:
    """Cache OHLCV bars in SQLite with optional Parquet snapshots."""

    def __init__(self, cache_dir: str = "data/cache") -> None:
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._cache_dir / "market_data_cache.sqlite"
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS market_data_cache (
                    symbol TEXT NOT NULL,
                    interval TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    provider TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    PRIMARY KEY (symbol, interval, timestamp)
                )
                """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_market_data_symbol_interval_time "
                "ON market_data_cache(symbol, interval, timestamp)"
            )
            conn.commit()

    def get(
        self,
        symbol: str,
        interval: str,
        start: pd.Timestamp,
        end: pd.Timestamp,
    ) -> Optional[pd.DataFrame]:
        start_ts = self._ensure_utc(start)
        end_ts = self._ensure_utc(end)
        query = (
            "SELECT timestamp, open, high, low, close, volume "
            "FROM market_data_cache "
            "WHERE symbol = ? AND interval = ? AND timestamp >= ? AND timestamp <= ? "
            "ORDER BY timestamp"
        )
        with sqlite3.connect(self._db_path) as conn:
            df = pd.read_sql_query(
                query,
                conn,
                params=(symbol, interval, start_ts.isoformat(), end_ts.isoformat()),
            )
        if df.empty:
            return None
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp")
        return df

    def put(self, symbol: str, interval: str, df: pd.DataFrame, provider: str) -> None:
        if df.empty:
            return

        df = self._normalize_frame(df)
        rows = []
        now_iso = datetime.now(timezone.utc).isoformat()
        for ts, row in df.iterrows():
            rows.append(
                (
                    symbol,
                    interval,
                    ts.isoformat(),
                    float(row["open"]),
                    float(row["high"]),
                    float(row["low"]),
                    float(row["close"]),
                    float(row.get("volume", 0.0)),
                    provider,
                    now_iso,
                )
            )

        with sqlite3.connect(self._db_path) as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO market_data_cache (
                    symbol, interval, timestamp, open, high, low, close, volume, provider, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()

        self._write_parquet(symbol, interval, df, provider)

    def missing_ranges(
        self,
        symbol: str,
        interval: str,
        start: pd.Timestamp,
        end: pd.Timestamp,
    ) -> List[Tuple[pd.Timestamp, pd.Timestamp]]:
        start_ts = self._ensure_utc(start)
        end_ts = self._ensure_utc(end)
        existing = self._fetch_timestamps(symbol, interval, start_ts, end_ts)
        if not existing:
            return [(start_ts, end_ts)]

        interval_delta = self._interval_to_timedelta(interval)
        if interval_delta is None:
            ranges: List[Tuple[pd.Timestamp, pd.Timestamp]] = []
            if existing[0] > start_ts:
                ranges.append((start_ts, existing[0]))
            if existing[-1] < end_ts:
                ranges.append((existing[-1], end_ts))
            return ranges

        missing: List[Tuple[pd.Timestamp, pd.Timestamp]] = []
        expected = start_ts
        for ts in existing:
            if ts - expected >= interval_delta:
                missing.append((expected, ts - interval_delta))
            if ts + interval_delta > expected:
                expected = ts + interval_delta
        if expected <= end_ts:
            missing.append((expected, end_ts))
        return missing

    def last_fetched(self, symbol: str, interval: str) -> Optional[datetime]:
        query = (
            "SELECT MAX(timestamp) AS latest_ts "
            "FROM market_data_cache "
            "WHERE symbol = ? AND interval = ?"
        )
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(query, (symbol, interval)).fetchone()
        if row is None or row[0] is None:
            return None
        return pd.to_datetime(row[0], utc=True).to_pydatetime()

    def _fetch_timestamps(
        self,
        symbol: str,
        interval: str,
        start: pd.Timestamp,
        end: pd.Timestamp,
    ) -> List[pd.Timestamp]:
        query = (
            "SELECT timestamp FROM market_data_cache "
            "WHERE symbol = ? AND interval = ? AND timestamp >= ? AND timestamp <= ? "
            "ORDER BY timestamp"
        )
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                query, (symbol, interval, start.isoformat(), end.isoformat())
            ).fetchall()
        return [pd.to_datetime(row[0], utc=True) for row in rows]

    def _write_parquet(self, symbol: str, interval: str, df: pd.DataFrame, provider: str) -> None:
        if not self._parquet_available():
            logger.warning("Parquet engine not available; skipping cache write")
            return
        df = self._normalize_frame(df)
        for month, month_df in df.groupby(df.index.to_period("M")):
            month_dir = (
                self._cache_dir / provider / symbol / interval / str(month).replace("/", "-")
            )
            month_dir.mkdir(parents=True, exist_ok=True)
            parquet_path = month_dir / "data.parquet"
            if parquet_path.exists():
                try:
                    existing = pd.read_parquet(parquet_path)
                    existing.index = pd.to_datetime(existing.index, utc=True)
                    combined = pd.concat([existing, month_df])
                    combined = combined[~combined.index.duplicated(keep="last")]
                    combined.sort_index(inplace=True)
                except Exception as exc:
                    logger.warning("Failed to read existing parquet %s: %s", parquet_path, exc)
                    combined = month_df
            else:
                combined = month_df
            combined.to_parquet(parquet_path)

    @staticmethod
    def _parquet_available() -> bool:
        return (
            importlib.util.find_spec("pyarrow") is not None
            or importlib.util.find_spec("fastparquet") is not None
        )

    @staticmethod
    def _normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
        normalized = df.copy()
        normalized.columns = [str(c).lower() for c in normalized.columns]
        idx = pd.to_datetime(normalized.index)
        if idx.tz is None:
            idx = idx.tz_localize(timezone.utc)
        else:
            idx = idx.tz_convert(timezone.utc)
        normalized.index = idx
        return normalized

    @staticmethod
    def _ensure_utc(ts: pd.Timestamp) -> pd.Timestamp:
        ts = pd.to_datetime(ts)
        if ts.tzinfo is None:
            return ts.tz_localize(timezone.utc)
        return ts.tz_convert(timezone.utc)

    @staticmethod
    def _interval_to_timedelta(interval: str) -> Optional[pd.Timedelta]:
        if not interval:
            return None
        unit = interval[-1]
        try:
            value = int(interval[:-1])
        except ValueError:
            return None
        if unit == "m":
            return pd.Timedelta(minutes=value)
        if unit == "h":
            return pd.Timedelta(hours=value)
        if unit == "d":
            return pd.Timedelta(days=value)
        if unit == "w":
            return pd.Timedelta(weeks=value)
        return None
