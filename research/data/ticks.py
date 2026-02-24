"""Tick data utilities for offline testing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd


@dataclass
class TickRow:
    symbol: str
    timestamp: pd.Timestamp
    price: float
    size: float
    bid: Optional[float]
    ask: Optional[float]


def _ensure_utc_index(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame index must be a DatetimeIndex")
    if df.index.tz is None:
        df = df.copy()
        df.index = df.index.tz_localize("UTC")
    else:
        df = df.copy()
        df.index = df.index.tz_convert("UTC")
    return df


def generate_synthetic_ticks(
    bars: pd.DataFrame,
    *,
    symbol: str,
    ticks_per_bar: int = 10,
    seed: int = 42,
    spread_bps: float = 5.0,
) -> pd.DataFrame:
    bars = _ensure_utc_index(bars)
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(bars.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    if ticks_per_bar <= 0:
        raise ValueError("ticks_per_bar must be positive")

    rng = np.random.default_rng(seed)
    records: List[dict] = []

    bars = bars.sort_index()
    for bar_ts, row in bars.iterrows():
        open_ = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        volume = float(row.get("volume", 0.0))

        if high < low:
            raise ValueError("Bar high must be >= low")

        times = pd.date_range(
            start=bar_ts,
            periods=ticks_per_bar,
            freq="1s",
            tz=bar_ts.tz,
        )
        base_path = np.linspace(open_, close, ticks_per_bar)
        noise_scale = (high - low) * 0.02
        noise = rng.normal(0.0, noise_scale, ticks_per_bar)
        prices = np.clip(base_path + noise, low, high)

        size_base = volume / ticks_per_bar if volume > 0 else 0.0
        size_noise = rng.uniform(0.5, 1.5, ticks_per_bar)
        sizes = size_base * size_noise

        spreads = prices * (spread_bps / 10000.0)
        bids = prices - spreads / 2
        asks = prices + spreads / 2

        for idx, tick_ts in enumerate(times):
            records.append(
                {
                    "symbol": symbol,
                    "timestamp": tick_ts,
                    "price": float(prices[idx]),
                    "size": float(sizes[idx]),
                    "bid": float(bids[idx]),
                    "ask": float(asks[idx]),
                }
            )

    return pd.DataFrame.from_records(records)


def validate_ticks(ticks: pd.DataFrame) -> None:
    required = {"symbol", "timestamp", "price", "size", "bid", "ask"}
    missing = required - set(ticks.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    timestamps = pd.to_datetime(ticks["timestamp"], utc=True)
    if timestamps.dt.tz is None:
        raise ValueError("Tick timestamps must be timezone-aware")

    if (ticks["price"] <= 0).any():
        raise ValueError("Tick prices must be positive")
    if (ticks["size"] < 0).any():
        raise ValueError("Tick sizes must be non-negative")
    if (ticks["bid"] > ticks["price"]).any() or (ticks["price"] > ticks["ask"]).any():
        raise ValueError("Tick bid/ask must surround price")

    ordered = ticks.sort_values(["symbol", "timestamp"])
    diffs = ordered.groupby("symbol")["timestamp"].diff()
    if diffs.dropna().lt(pd.Timedelta(0)).any():
        raise ValueError("Tick timestamps must be non-decreasing per symbol")


def aggregate_ticks(ticks: pd.DataFrame, *, freq: str = "1min") -> pd.DataFrame:
    required = {"symbol", "timestamp", "price", "size"}
    missing = required - set(ticks.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    ticks = ticks.copy()
    ticks["timestamp"] = pd.to_datetime(ticks["timestamp"], utc=True)
    ticks = ticks.sort_values(["symbol", "timestamp"])

    grouped = ticks.set_index("timestamp").groupby("symbol").resample(freq)
    ohlc = grouped["price"].ohlc()
    volume = grouped["size"].sum().rename("volume")

    combined = ohlc.join(volume)
    combined = combined.reset_index().dropna(subset=["open", "high", "low", "close"])
    return combined
