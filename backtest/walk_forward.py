"""Walk-forward validation harness for parameter robustness testing."""

import json
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import timedelta
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

import pandas as pd

from backtest.engine import BacktestEngine, BacktestResults
from config.settings import Settings, WalkForwardConfig
from src.strategies.base import BaseStrategy


@dataclass
class WalkForwardWindowResult:
    """Per-window in-sample and out-of-sample evaluation result."""

    window_index: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    train_results: BacktestResults
    test_results: BacktestResults
    best_params: Dict[str, Any] = field(default_factory=dict)

    @property
    def sharpe_retention_pct(self) -> float:
        train_sharpe = self.train_results.sharpe_ratio
        test_sharpe = self.test_results.sharpe_ratio
        if train_sharpe == 0:
            return 0.0
        return (test_sharpe / train_sharpe) * 100


@dataclass
class WalkForwardResults:
    """Aggregated walk-forward validation output."""

    windows: List[WalkForwardWindowResult] = field(default_factory=list)

    @property
    def num_windows(self) -> int:
        return len(self.windows)

    @property
    def avg_train_sharpe(self) -> float:
        if not self.windows:
            return 0.0
        return sum(w.train_results.sharpe_ratio for w in self.windows) / len(self.windows)

    @property
    def avg_test_sharpe(self) -> float:
        if not self.windows:
            return 0.0
        return sum(w.test_results.sharpe_ratio for w in self.windows) / len(self.windows)

    @property
    def avg_train_return_pct(self) -> float:
        if not self.windows:
            return 0.0
        return sum(w.train_results.total_return_pct for w in self.windows) / len(self.windows)

    @property
    def avg_test_return_pct(self) -> float:
        if not self.windows:
            return 0.0
        return sum(w.test_results.total_return_pct for w in self.windows) / len(self.windows)

    @property
    def avg_sharpe_retention_pct(self) -> float:
        if not self.windows:
            return 0.0
        return sum(w.sharpe_retention_pct for w in self.windows) / len(self.windows)

    @property
    def avg_train_max_drawdown_pct(self) -> float:
        if not self.windows:
            return 0.0
        return sum(w.train_results.max_drawdown_pct for w in self.windows) / len(self.windows)

    @property
    def avg_test_max_drawdown_pct(self) -> float:
        if not self.windows:
            return 0.0
        return sum(w.test_results.max_drawdown_pct for w in self.windows) / len(self.windows)

    @property
    def overfitting_ratio(self) -> float:
        train_abs = abs(self.avg_train_return_pct)
        test_abs = abs(self.avg_test_return_pct)
        if train_abs <= 1e-9:
            return 0.0
        return max(0.0, (train_abs - test_abs) / train_abs)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize walk-forward results to a JSON-compatible dictionary."""
        return {
            "num_windows": self.num_windows,
            "avg_train_sharpe": self.avg_train_sharpe,
            "avg_test_sharpe": self.avg_test_sharpe,
            "avg_train_return_pct": self.avg_train_return_pct,
            "avg_test_return_pct": self.avg_test_return_pct,
            "avg_train_max_drawdown_pct": self.avg_train_max_drawdown_pct,
            "avg_test_max_drawdown_pct": self.avg_test_max_drawdown_pct,
            "avg_sharpe_retention_pct": self.avg_sharpe_retention_pct,
            "overfitting_ratio": self.overfitting_ratio,
            "windows": [
                {
                    "window_index": result.window_index,
                    "train_start": result.train_start,
                    "train_end": result.train_end,
                    "test_start": result.test_start,
                    "test_end": result.test_end,
                    "best_params": result.best_params,
                    "train": {
                        "total_return_pct": result.train_results.total_return_pct,
                        "sharpe_ratio": result.train_results.sharpe_ratio,
                        "max_drawdown_pct": result.train_results.max_drawdown_pct,
                    },
                    "test": {
                        "total_return_pct": result.test_results.total_return_pct,
                        "sharpe_ratio": result.test_results.sharpe_ratio,
                        "max_drawdown_pct": result.test_results.max_drawdown_pct,
                    },
                }
                for result in self.windows
            ],
        }

    def print_report(self) -> None:
        print("\n" + "=" * 68)
        print("  WALK-FORWARD VALIDATION")
        print("=" * 68)
        print(f"  Windows                 : {self.num_windows:>8}")
        print(f"  Avg Train Return        : {self.avg_train_return_pct:>8.2f}%")
        print(f"  Avg Test Return         : {self.avg_test_return_pct:>8.2f}%")
        print(f"  Avg Train Sharpe        : {self.avg_train_sharpe:>8.2f}")
        print(f"  Avg Test Sharpe         : {self.avg_test_sharpe:>8.2f}")
        print(f"  Avg Sharpe Retention    : {self.avg_sharpe_retention_pct:>8.2f}%")
        print("=" * 68)

        for w in self.windows:
            print(
                f"  W{w.window_index:02d} "
                f"train {w.train_start}→{w.train_end} "
                f"test {w.test_start}→{w.test_end}  "
                f"train_sharpe={w.train_results.sharpe_ratio:>5.2f} "
                f"test_sharpe={w.test_results.sharpe_ratio:>5.2f}"
            )
        print()


class WalkForwardHarness:
    """Run walk-forward validation with in-sample parameter search.

    Parameters
    ----------
    settings
        Global settings object.
    strategy_cls
        Strategy class to instantiate for each backtest run.
    config
        Walk-forward split, scoring, and parameter-grid settings.
    """

    def __init__(
        self,
        settings: Settings,
        strategy_cls: Type[BaseStrategy],
        config: Optional[WalkForwardConfig] = None,
    ):
        self.settings = settings
        self.strategy_cls = strategy_cls
        self.config = config or settings.walk_forward

        if self.config.n_splits <= 0:
            raise ValueError("n_splits must be > 0")
        if self.config.in_sample_ratio <= 0 or self.config.in_sample_ratio >= 1:
            raise ValueError("in_sample_ratio must be in (0, 1)")
        window_type = str(self.config.window_type).strip().lower()
        if window_type not in {"expanding", "rolling"}:
            raise ValueError("window_type must be 'expanding' or 'rolling'")

    def _build_windows(self, start: str, end: str) -> List[dict]:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        if start_ts >= end_ts:
            return []

        total_days = (end_ts - start_ts).days + 1
        split_days = max(2, total_days // self.config.n_splits)
        in_sample_days = max(1, int(split_days * self.config.in_sample_ratio))

        windows: List[dict] = []
        window_type = str(self.config.window_type).strip().lower()

        for idx in range(self.config.n_splits):
            split_start = start_ts + timedelta(days=idx * split_days)
            if split_start > end_ts:
                break

            split_end = split_start + timedelta(days=split_days - 1)
            if idx == self.config.n_splits - 1:
                split_end = end_ts
            split_end = min(split_end, end_ts)

            train_start = start_ts if window_type == "expanding" else split_start
            train_end = split_start + timedelta(days=in_sample_days - 1)
            train_end = min(train_end, split_end)

            test_start = train_end + timedelta(days=1)
            if test_start > split_end:
                continue

            windows.append(
                {
                    "window_index": len(windows) + 1,
                    "train_start": train_start.strftime("%Y-%m-%d"),
                    "train_end": train_end.strftime("%Y-%m-%d"),
                    "test_start": test_start.strftime("%Y-%m-%d"),
                    "test_end": split_end.strftime("%Y-%m-%d"),
                }
            )

        return windows

    def _iter_param_sets(self) -> List[Dict[str, Any]]:
        param_grid = self.config.param_grid or {}
        if not param_grid:
            return [{}]

        keys = list(param_grid.keys())
        value_lists = [param_grid[key] for key in keys]
        return [dict(zip(keys, combo)) for combo in product(*value_lists)]

    @staticmethod
    def _apply_overrides(settings: Settings, overrides: Dict[str, Any]) -> Settings:
        adjusted = deepcopy(settings)
        for dotted_path, value in overrides.items():
            node: Any = adjusted
            parts = dotted_path.split(".")
            for part in parts[:-1]:
                node = getattr(node, part)
            setattr(node, parts[-1], value)
        return adjusted

    def _score(self, result: BacktestResults) -> float:
        metric_name = str(self.config.score_metric or "sharpe_ratio")
        metric_value = getattr(result, metric_name, None)
        if metric_value is None:
            metric_value = result.sharpe_ratio
        return float(metric_value)

    def _run_backtest(self, settings: Settings, start: str, end: str) -> BacktestResults:
        strategy = self.strategy_cls(settings)
        engine = BacktestEngine(settings, strategy)
        return engine.run(start, end)

    def _persist(self, results: WalkForwardResults) -> None:
        output_path = Path(self.config.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(results.to_dict(), indent=2), encoding="utf-8")

    def run(self, start: str, end: str) -> WalkForwardResults:
        windows = self._build_windows(start, end)
        results = WalkForwardResults()

        for window in windows:
            best_train_result: Optional[BacktestResults] = None
            best_params: Dict[str, Any] = {}
            best_score: Optional[float] = None

            for params in self._iter_param_sets():
                tuned_settings = self._apply_overrides(self.settings, params)
                train_results = self._run_backtest(
                    tuned_settings,
                    window["train_start"],
                    window["train_end"],
                )
                candidate_score = self._score(train_results)
                if best_score is None or candidate_score > best_score:
                    best_score = candidate_score
                    best_params = params
                    best_train_result = train_results

            if best_train_result is None:
                continue

            test_settings = self._apply_overrides(self.settings, best_params)
            test_results = self._run_backtest(
                test_settings,
                window["test_start"],
                window["test_end"],
            )

            results.windows.append(
                WalkForwardWindowResult(
                    window_index=window["window_index"],
                    train_start=window["train_start"],
                    train_end=window["train_end"],
                    test_start=window["test_start"],
                    test_end=window["test_end"],
                    train_results=best_train_result,
                    test_results=test_results,
                    best_params=best_params,
                )
            )

        self._persist(results)
        return results


class WalkForwardEngine:
    """Backward-compatible wrapper for month-based walk-forward execution."""

    def __init__(
        self,
        settings: Settings,
        strategy_cls: Type[BaseStrategy],
        train_months: int = 6,
        test_months: int = 1,
        step_months: int = 1,
    ):
        if train_months <= 0 or test_months <= 0 or step_months <= 0:
            raise ValueError("train_months, test_months and step_months must be > 0")
        self.settings = settings
        self.strategy_cls = strategy_cls
        self.train_months = train_months
        self.test_months = test_months
        self.step_months = step_months

    def _build_windows(self, start: str, end: str) -> List[dict]:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        if start_ts >= end_ts:
            return []

        windows: List[dict] = []
        cursor = start_ts
        idx = 1

        while True:
            train_start = cursor
            train_end = train_start + pd.DateOffset(months=self.train_months) - timedelta(days=1)
            test_start = train_end + timedelta(days=1)
            test_end = test_start + pd.DateOffset(months=self.test_months) - timedelta(days=1)

            if test_end > end_ts:
                break

            windows.append(
                {
                    "window_index": idx,
                    "train_start": train_start.strftime("%Y-%m-%d"),
                    "train_end": train_end.strftime("%Y-%m-%d"),
                    "test_start": test_start.strftime("%Y-%m-%d"),
                    "test_end": test_end.strftime("%Y-%m-%d"),
                }
            )

            idx += 1
            cursor = cursor + pd.DateOffset(months=self.step_months)

        return windows

    def run(self, start: str, end: str) -> WalkForwardResults:
        windows = self._build_windows(start, end)
        results = WalkForwardResults()

        for window in windows:
            train_strategy = self.strategy_cls(self.settings)
            train_engine = BacktestEngine(self.settings, train_strategy)
            train_results = train_engine.run(window["train_start"], window["train_end"])

            test_strategy = self.strategy_cls(self.settings)
            test_engine = BacktestEngine(self.settings, test_strategy)
            test_results = test_engine.run(window["test_start"], window["test_end"])

            results.windows.append(
                WalkForwardWindowResult(
                    window_index=window["window_index"],
                    train_start=window["train_start"],
                    train_end=window["train_end"],
                    test_start=window["test_start"],
                    test_end=window["test_end"],
                    train_results=train_results,
                    test_results=test_results,
                )
            )

        output_path = Path(self.settings.walk_forward.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(results.to_dict(), indent=2), encoding="utf-8")
        return results
