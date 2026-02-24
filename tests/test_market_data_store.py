from datetime import datetime, timezone

import pandas as pd
import pytest

from src.data.market_data_store import MarketDataStore


def _sample_df(index):
    return pd.DataFrame(
        {
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.5, 100.5],
            "close": [100.5, 101.5],
            "volume": [1000.0, 1100.0],
        },
        index=index,
    )


def test_put_and_get_roundtrip(tmp_path):
    store = MarketDataStore(cache_dir=str(tmp_path))
    idx = pd.DatetimeIndex(["2024-01-01", "2024-01-02"], tz="UTC")
    df = _sample_df(idx)

    store.put("AAPL", "1d", df, "yfinance")
    result = store.get(
        "AAPL",
        "1d",
        pd.Timestamp("2024-01-01", tz="UTC"),
        pd.Timestamp("2024-01-02", tz="UTC"),
    )

    assert result is not None
    assert list(result.columns) == ["open", "high", "low", "close", "volume"]
    assert len(result) == 2
    assert result.index.tz is not None
    assert str(result.index.tz) == "UTC"


def test_missing_ranges_returns_full_when_empty(tmp_path):
    store = MarketDataStore(cache_dir=str(tmp_path))
    start = pd.Timestamp("2024-01-01", tz="UTC")
    end = pd.Timestamp("2024-01-05", tz="UTC")

    missing = store.missing_ranges("AAPL", "1d", start, end)

    assert missing == [(start, end)]


def test_missing_ranges_detects_gap(tmp_path):
    store = MarketDataStore(cache_dir=str(tmp_path))
    idx = pd.DatetimeIndex(["2024-01-01", "2024-01-03"], tz="UTC")
    df = _sample_df(idx)
    store.put("AAPL", "1d", df, "yfinance")

    start = pd.Timestamp("2024-01-01", tz="UTC")
    end = pd.Timestamp("2024-01-03", tz="UTC")
    missing = store.missing_ranges("AAPL", "1d", start, end)

    assert len(missing) == 1
    gap_start, gap_end = missing[0]
    assert gap_start <= pd.Timestamp("2024-01-02", tz="UTC") <= gap_end


def test_dedup_reinsert(tmp_path):
    store = MarketDataStore(cache_dir=str(tmp_path))
    idx = pd.DatetimeIndex(["2024-01-01", "2024-01-02"], tz="UTC")
    df = _sample_df(idx)

    store.put("AAPL", "1d", df, "yfinance")
    store.put("AAPL", "1d", df, "yfinance")

    result = store.get(
        "AAPL",
        "1d",
        pd.Timestamp("2024-01-01", tz="UTC"),
        pd.Timestamp("2024-01-02", tz="UTC"),
    )

    assert result is not None
    assert len(result) == 2


def test_parquet_written(tmp_path):
    pytest.importorskip("pyarrow")
    store = MarketDataStore(cache_dir=str(tmp_path))
    idx = pd.DatetimeIndex(["2024-02-01", "2024-02-02"], tz="UTC")
    df = _sample_df(idx)

    store.put("AAPL", "1d", df, "yfinance")

    parquet_path = tmp_path / "yfinance" / "AAPL" / "1d" / "2024-02" / "data.parquet"
    assert parquet_path.exists()

    loaded = pd.read_parquet(parquet_path)
    assert not loaded.empty


def test_last_fetched_returns_latest(tmp_path):
    store = MarketDataStore(cache_dir=str(tmp_path))
    idx = pd.DatetimeIndex(["2024-01-01", "2024-01-02"], tz="UTC")
    df = _sample_df(idx)

    store.put("AAPL", "1d", df, "yfinance")
    last = store.last_fetched("AAPL", "1d")

    assert isinstance(last, datetime)
    assert last.tzinfo == timezone.utc
