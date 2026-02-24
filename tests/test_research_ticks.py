import pandas as pd
import pytest

from research.data.ticks import aggregate_ticks, generate_synthetic_ticks, validate_ticks


def _bars_df():
    index = pd.date_range("2026-02-20", periods=2, freq="D", tz="UTC")
    return pd.DataFrame(
        {
            "open": [100.0, 102.0],
            "high": [105.0, 106.0],
            "low": [99.0, 101.0],
            "close": [104.0, 103.0],
            "volume": [1000.0, 800.0],
        },
        index=index,
    )


def test_generate_synthetic_ticks_and_validate():
    ticks = generate_synthetic_ticks(_bars_df(), symbol="TEST", ticks_per_bar=5, seed=7)
    assert len(ticks) == 10
    assert {"symbol", "timestamp", "price", "size", "bid", "ask"}.issubset(ticks.columns)
    validate_ticks(ticks)


def test_aggregate_ticks():
    ticks = generate_synthetic_ticks(_bars_df(), symbol="TEST", ticks_per_bar=3, seed=1)
    aggregated = aggregate_ticks(ticks, freq="1s")
    assert {"open", "high", "low", "close", "volume"}.issubset(aggregated.columns)
    assert (aggregated["volume"] > 0).any()


def test_validate_ticks_rejects_negative_price():
    ticks = generate_synthetic_ticks(_bars_df(), symbol="TEST", ticks_per_bar=2)
    ticks.loc[ticks.index[0], "price"] = -1.0
    with pytest.raises(ValueError, match="Tick prices must be positive"):
        validate_ticks(ticks)
