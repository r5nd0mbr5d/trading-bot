"""Unit tests for walk-forward validation engine."""

from backtest.engine import BacktestResults
from backtest.walk_forward import WalkForwardEngine
from config.settings import Settings
from src.strategies.ma_crossover import MACrossoverStrategy


def test_build_windows_count_for_12_month_period():
    settings = Settings()
    engine = WalkForwardEngine(
        settings,
        MACrossoverStrategy,
        train_months=6,
        test_months=1,
        step_months=1,
    )

    windows = engine._build_windows("2022-01-01", "2022-12-31")
    assert len(windows) == 6
    assert windows[0]["train_start"] == "2022-01-01"
    assert windows[0]["test_start"] == "2022-07-01"


def test_run_executes_train_and_test_backtests(monkeypatch):
    settings = Settings()
    engine = WalkForwardEngine(
        settings,
        MACrossoverStrategy,
        train_months=6,
        test_months=1,
        step_months=1,
    )

    calls = []

    def fake_run(self, start, end):
        calls.append((start, end))
        return BacktestResults(initial_capital=100_000.0, final_value=101_000.0)

    monkeypatch.setattr("backtest.walk_forward.BacktestEngine.run", fake_run)

    results = engine.run("2022-01-01", "2022-12-31")
    assert results.num_windows == 6
    assert len(calls) == 12


def test_results_aggregate_metrics(monkeypatch):
    settings = Settings()
    engine = WalkForwardEngine(
        settings,
        MACrossoverStrategy,
        train_months=6,
        test_months=1,
        step_months=1,
    )

    def fake_run(self, start, end):
        month = int(start.split("-")[1])
        base = 100_000.0
        bump = month * 100
        return BacktestResults(initial_capital=base, final_value=base + bump)

    monkeypatch.setattr("backtest.walk_forward.BacktestEngine.run", fake_run)

    results = engine.run("2022-01-01", "2022-12-31")
    assert results.num_windows == 6
    assert results.avg_train_return_pct > 0
    assert results.avg_test_return_pct > 0


def test_invalid_window_sizes_raise_value_error():
    settings = Settings()
    try:
        WalkForwardEngine(settings, MACrossoverStrategy, train_months=0)
        assert False, "Expected ValueError for train_months=0"
    except ValueError:
        pass
