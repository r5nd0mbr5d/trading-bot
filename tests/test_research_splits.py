"""Tests for research split utilities."""

import pandas as pd

from research.data.splits import apply_gap, apply_scaler, fit_scaler


def _make_df(start: str, days: int) -> pd.DataFrame:
    idx = pd.date_range(start, periods=days, freq="D", tz="UTC")
    return pd.DataFrame({"feat": range(days)}, index=idx)


def test_apply_gap_drops_boundary_rows():
    train = _make_df("2024-01-01", 5)
    val = _make_df("2024-01-06", 5)
    test = _make_df("2024-01-11", 5)

    train_out, val_out, test_out = apply_gap(train, val, test, gap_days=2)

    assert len(train_out) == 5
    assert val_out.index.min() > train.index.max() + pd.Timedelta(days=2)
    assert test_out.index.min() > val_out.index.max() + pd.Timedelta(days=2)


def test_scaler_uses_train_stats_only():
    train = _make_df("2024-01-01", 5)
    val = _make_df("2024-01-06", 5)

    stats = fit_scaler(train, ["feat"])
    scaled_val = apply_scaler(val, stats, ["feat"])

    assert (
        abs(
            scaled_val["feat"].mean()
            - ((val["feat"].mean() - train["feat"].mean()) / train["feat"].std(ddof=0))
        )
        < 1e-6
    )
