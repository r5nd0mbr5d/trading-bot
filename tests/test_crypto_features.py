"""Tests for Step 57 BTC crypto feature engineering."""

from __future__ import annotations

import numpy as np
import pandas as pd

from research.data.crypto_features import (
    build_crypto_features,
    drop_nan_feature_rows,
    get_feature_columns,
)


def _sample_ohlcv(periods: int = 140) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=periods, freq="D", tz="UTC")
    base = 10000 + np.linspace(0.0, 500.0, periods)
    return pd.DataFrame(
        {
            "open": base - 10,
            "high": base + 20,
            "low": base - 20,
            "close": base + 5,
            "volume": np.linspace(1000, 4000, periods),
        },
        index=index,
    )


def test_feature_count():
    features = build_crypto_features(_sample_ohlcv())

    assert features.shape[1] == 20


def test_feature_names_match_spec():
    features = build_crypto_features(_sample_ohlcv())

    assert list(features.columns) == get_feature_columns()


def test_no_lookahead_ema():
    source = _sample_ohlcv()
    base_features = build_crypto_features(source)

    modified = source.copy()
    modified.iloc[-1, modified.columns.get_loc("close")] = modified.iloc[-1]["close"] * 5
    modified_features = build_crypto_features(modified)

    assert np.isclose(
        base_features.iloc[-2]["ema_5_pct"],
        modified_features.iloc[-2]["ema_5_pct"],
        equal_nan=True,
    )


def test_no_lookahead_rsi():
    source = _sample_ohlcv()
    base_features = build_crypto_features(source)

    modified = source.copy()
    modified.iloc[-1, modified.columns.get_loc("close")] = modified.iloc[-1]["close"] * 3
    modified_features = build_crypto_features(modified)

    assert np.isclose(
        base_features.iloc[-2]["rsi_5"],
        modified_features.iloc[-2]["rsi_5"],
        equal_nan=True,
    )


def test_no_lookahead_atr():
    source = _sample_ohlcv()
    base_features = build_crypto_features(source)

    modified = source.copy()
    modified.iloc[-1, modified.columns.get_loc("high")] = modified.iloc[-1]["high"] * 2
    modified_features = build_crypto_features(modified)

    assert np.isclose(
        base_features.iloc[-2]["atr_pct_20"],
        modified_features.iloc[-2]["atr_pct_20"],
        equal_nan=True,
    )


def test_bounded_rsi():
    features = build_crypto_features(_sample_ohlcv())

    values = features["rsi_20"].dropna()
    assert (values >= 0).all()
    assert (values <= 100).all()


def test_bounded_mfi():
    features = build_crypto_features(_sample_ohlcv())

    values = features["mfi_14"].dropna()
    assert (values >= 0).all()
    assert (values <= 100).all()


def test_bounded_cmf():
    features = build_crypto_features(_sample_ohlcv())

    values = features["cmf_20"].dropna()
    assert (values >= -1).all()
    assert (values <= 1).all()


def test_nan_handling_insufficient_bars():
    features = build_crypto_features(_sample_ohlcv(periods=10))

    assert features["ema_60_pct"].isna().all()
    assert features["obv_ratio_60"].isna().all()


def test_nan_rows_dropped_counted():
    features = build_crypto_features(_sample_ohlcv(periods=30))
    cleaned, dropped = drop_nan_feature_rows(features)

    assert dropped > 0
    assert len(cleaned) < len(features)


def test_ffill_bounded_at_3():
    source = _sample_ohlcv(periods=20)
    source = source.drop(source.index[[5, 6, 7, 8, 9]])

    features = build_crypto_features(source, config={"max_ffill_bars": 3})

    idx = pd.date_range("2024-01-06", periods=5, freq="D", tz="UTC")
    assert features.loc[idx[0], "ema_5_pct"] == features.loc[idx[0], "ema_5_pct"]
    assert features.loc[idx[1], "ema_5_pct"] == features.loc[idx[1], "ema_5_pct"]
    assert features.loc[idx[2], "ema_5_pct"] == features.loc[idx[2], "ema_5_pct"]
    assert np.isnan(features.loc[idx[3], "ema_5_pct"])
    assert np.isnan(features.loc[idx[4], "ema_5_pct"])


def test_utc_aware_index():
    source = _sample_ohlcv()
    source.index = source.index.tz_convert(None)

    features = build_crypto_features(source)

    assert isinstance(features.index, pd.DatetimeIndex)
    assert str(features.index.tz) == "UTC"


def test_zero_volume_handling():
    source = _sample_ohlcv()
    source.iloc[30, source.columns.get_loc("volume")] = 0.0

    features = build_crypto_features(source)

    row = features.iloc[30]
    assert np.isnan(row["obv_ratio_20"])
    assert np.isnan(row["mfi_14"])
    assert np.isnan(row["cmf_20"])


def test_empty_dataframe_returns_empty():
    empty = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    empty.index = pd.DatetimeIndex([], tz="UTC")

    features = build_crypto_features(empty)

    assert features.empty
    assert list(features.columns) == get_feature_columns()
