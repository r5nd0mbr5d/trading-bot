"""Unit tests for walk-forward validation harness."""

import json

from backtest.engine import BacktestResults
from backtest.walk_forward import WalkForwardEngine, WalkForwardHarness
from config.settings import Settings
from src.data.models import Signal
from src.strategies.base import BaseStrategy


class MockStrategy(BaseStrategy):
    """No-op strategy used to isolate harness behaviour in tests."""

    def generate_signal(self, symbol: str) -> Signal | None:
        _ = symbol
        return None


def test_build_windows_count_for_annual_period():
    settings = Settings()
    settings.walk_forward.n_splits = 8
    settings.walk_forward.in_sample_ratio = 0.7
    harness = WalkForwardHarness(settings, MockStrategy)

    windows = harness._build_windows("2022-01-01", "2022-12-31")
    assert len(windows) == 8
    assert windows[0]["train_start"] == "2022-01-01"


def test_run_executes_grid_search_and_oos_backtests(monkeypatch, tmp_path):
    settings = Settings()
    settings.walk_forward.n_splits = 4
    settings.walk_forward.in_sample_ratio = 0.7
    settings.walk_forward.score_metric = "total_return_pct"
    settings.walk_forward.param_grid = {
        "strategy.fast_period": [5, 20],
        "strategy.slow_period": [30],
    }
    settings.walk_forward.output_path = str(tmp_path / "walk_forward_results.json")
    harness = WalkForwardHarness(settings, MockStrategy)

    calls = []

    def fake_run(self, start, end):
        calls.append((self.settings.strategy.fast_period, start, end))
        base_value = 100_000.0
        bonus = 1_000.0 if self.settings.strategy.fast_period == 5 else 300.0
        return BacktestResults(initial_capital=base_value, final_value=base_value + bonus)

    monkeypatch.setattr("backtest.walk_forward.BacktestEngine.run", fake_run)

    results = harness.run("2022-01-01", "2022-12-31")

    assert results.num_windows == 4
    assert all(window.best_params["strategy.fast_period"] == 5 for window in results.windows)
    assert len(calls) == 12  # 2 train runs per window + 1 OOS run per window


def test_results_aggregate_metrics_and_json_output(monkeypatch, tmp_path):
    settings = Settings()
    settings.walk_forward.n_splits = 3
    settings.walk_forward.in_sample_ratio = 0.6
    settings.walk_forward.score_metric = "total_return_pct"
    settings.walk_forward.output_path = str(tmp_path / "walk_forward_results.json")
    harness = WalkForwardHarness(settings, MockStrategy)

    def fake_run(self, start, end):
        _ = (start, end)
        return BacktestResults(initial_capital=100_000.0, final_value=101_000.0)

    monkeypatch.setattr("backtest.walk_forward.BacktestEngine.run", fake_run)

    results = harness.run("2022-01-01", "2022-12-31")
    assert results.num_windows == 3
    assert results.avg_train_return_pct > 0
    assert results.avg_test_return_pct > 0
    assert results.overfitting_ratio >= 0

    output_path = tmp_path / "walk_forward_results.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["num_windows"] == 3
    assert "overfitting_ratio" in payload


def test_invalid_harness_config_raises_value_error():
    settings = Settings()
    settings.walk_forward.in_sample_ratio = 1.0
    try:
        WalkForwardHarness(settings, MockStrategy)
        assert False, "Expected ValueError for in_sample_ratio=1.0"
    except ValueError:
        pass


def test_month_based_engine_remains_compatible(monkeypatch, tmp_path):
    settings = Settings()
    settings.walk_forward.output_path = str(tmp_path / "walk_forward_results.json")
    engine = WalkForwardEngine(settings, MockStrategy, train_months=6, test_months=1, step_months=1)

    def fake_run(self, start, end):
        _ = (start, end)
        return BacktestResults(initial_capital=100_000.0, final_value=100_500.0)

    monkeypatch.setattr("backtest.walk_forward.BacktestEngine.run", fake_run)

    results = engine.run("2022-01-01", "2022-12-31")
    assert results.num_windows == 6
