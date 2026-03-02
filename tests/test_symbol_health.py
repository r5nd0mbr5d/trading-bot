"""Unit tests for symbol-universe health and remediation policy."""

from __future__ import annotations

import pandas as pd

from config.settings import Settings
from src.data.symbol_health import apply_symbol_universe_policy, evaluate_symbol_universe_health


def _frame_with_rows(rows: int) -> pd.DataFrame:
    return pd.DataFrame(
        {"open": [1.0] * rows, "high": [1.0] * rows, "low": [1.0] * rows, "close": [1.0] * rows},
        index=pd.date_range("2026-01-01", periods=rows, freq="min", tz="UTC"),
    )


class _FakeFeed:
    def __init__(self, rows_by_symbol: dict[str, int]):
        self._rows_by_symbol = rows_by_symbol

    def fetch_historical(self, symbol: str, period: str, interval: str):
        _ = (period, interval)
        rows = self._rows_by_symbol.get(symbol, 0)
        if rows <= 0:
            return pd.DataFrame()
        return _frame_with_rows(rows)


def test_evaluate_symbol_universe_health_computes_ratio_and_counts() -> None:
    settings = Settings()
    settings.data.symbols = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    settings.symbol_universe_min_bars_per_symbol = 100
    feed = _FakeFeed({"AAA": 120, "BBB": 90, "CCC": 130, "DDD": 0, "EEE": 101})

    summary = evaluate_symbol_universe_health(settings, feed=feed)

    assert summary["total_symbols"] == 5
    assert summary["healthy_symbols"] == 3
    assert summary["availability_ratio"] == 0.6
    assert summary["healthy_symbol_list"] == ["AAA", "CCC", "EEE"]


def test_apply_symbol_policy_blocks_when_strict_and_ratio_below_threshold() -> None:
    settings = Settings()
    settings.data.symbols = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    settings.symbol_universe_min_availability_ratio = 0.8
    settings.symbol_universe_min_bars_per_symbol = 100
    settings.symbol_universe_strict_mode = True
    settings.symbol_universe_remediation_enabled = False
    feed = _FakeFeed({"AAA": 120, "BBB": 90, "CCC": 130, "DDD": 0, "EEE": 101})

    decision = apply_symbol_universe_policy(settings, feed=feed)

    assert decision["allowed"] is False
    assert decision["remediated"] is False
    assert decision["reason"] == "insufficient_availability"


def test_apply_symbol_policy_remediates_with_deterministic_subset() -> None:
    settings = Settings()
    settings.data.symbols = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    settings.symbol_universe_min_availability_ratio = 0.8
    settings.symbol_universe_min_bars_per_symbol = 100
    settings.symbol_universe_strict_mode = True
    settings.symbol_universe_remediation_enabled = True
    settings.symbol_universe_remediation_min_symbols = 2
    settings.symbol_universe_remediation_target_symbols = 2
    feed = _FakeFeed({"AAA": 120, "BBB": 90, "CCC": 130, "DDD": 0, "EEE": 101})

    decision = apply_symbol_universe_policy(settings, feed=feed)

    assert decision["allowed"] is True
    assert decision["remediated"] is True
    assert decision["selected_symbols"] == ["AAA", "CCC"]
    assert decision["removed_symbols"] == ["BBB", "DDD", "EEE"]
