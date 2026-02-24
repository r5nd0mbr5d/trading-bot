"""Tests for research feature and label generation utilities."""

import numpy as np
import pandas as pd

from research.data.features import (
    add_cross_sectional_features,
    build_drop_manifest,
    compute_features,
    drop_nan_rows,
)
from research.data.labels import compute_labels, compute_thresholds
from research.data.snapshots import save_snapshot


def _sample_ohlcv() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=60, freq="D", tz="UTC")
    base = np.linspace(100.0, 110.0, len(idx))
    return pd.DataFrame(
        {
            "open": base,
            "high": base + 1.0,
            "low": base - 1.0,
            "close": base + 0.5,
            "volume": np.linspace(1000, 2000, len(idx)),
        },
        index=idx,
    )


def test_compute_features_returns_expected_columns():
    df = _sample_ohlcv()
    features = compute_features(df, symbol="TEST")

    assert "symbol" in features.columns
    assert "date" in features.columns
    assert "atr_pct" in features.columns
    assert "rsi_14" in features.columns
    assert "macd_hist" in features.columns
    assert "stoch_k" in features.columns
    assert "beta_20d" in features.columns


def test_drop_nan_rows_reduces_frame():
    df = _sample_ohlcv()
    features = compute_features(df, symbol="TEST")
    cleaned, dropped = drop_nan_rows(features)

    assert dropped > 0
    assert len(cleaned) < len(features)


def test_cross_sectional_ranks_added():
    df = _sample_ohlcv()
    features_a = compute_features(df, symbol="AAA")
    features_b = compute_features(df * 1.01, symbol="BBB")
    combined = pd.concat([features_a, features_b], ignore_index=True)

    ranked = add_cross_sectional_features(combined)
    assert "cs_rank_return_5d" in ranked.columns
    assert "cs_rank_vol" in ranked.columns
    assert "cs_rank_rsi" in ranked.columns


def test_drop_manifest_written_to_snapshot(tmp_path):
    df = _sample_ohlcv()
    features = compute_features(df, symbol="TEST")
    cleaned, dropped = drop_nan_rows(features)
    manifest = build_drop_manifest(dropped, len(features))

    artifact = save_snapshot(
        cleaned,
        str(tmp_path),
        {"symbols": ["TEST"], "timeframe": "1d"},
        snapshot_id="feat_snap",
        extra_metadata=manifest,
    )

    assert artifact.metadata["nan_dropped_rows"] == dropped
    assert artifact.metadata["nan_total_rows"] == len(features)


def test_compute_labels_uses_future_returns():
    df = _sample_ohlcv()
    thresholds = compute_thresholds(df["close"].pct_change())
    labels = compute_labels(
        df,
        symbol="TEST",
        horizon_days=5,
        thresholds=thresholds,
        fold_id=1,
        horizon_id="H5",
    )

    assert "forward_return" in labels.columns
    assert labels["forward_return"].iloc[0] != labels["forward_return"].iloc[1]
    assert labels["label_binary"].isin([0, 1]).all()
    assert labels["label_ternary"].isin([-1, 0, 1]).all()
