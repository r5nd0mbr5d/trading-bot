"""Walk-forward validation engine for robustness testing.

Runs rolling train/test windows to evaluate whether a strategy generalises
out-of-sample instead of overfitting one static date range.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import List, Type

import pandas as pd

from backtest.engine import BacktestEngine, BacktestResults
from config.settings import Settings
from src.strategies.base import BaseStrategy


@dataclass
class WalkForwardWindowResult:
    window_index: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    train_results: BacktestResults
    test_results: BacktestResults

    @property
    def sharpe_retention_pct(self) -> float:
        train_sharpe = self.train_results.sharpe_ratio
        test_sharpe = self.test_results.sharpe_ratio
        if train_sharpe == 0:
            return 0.0
        return (test_sharpe / train_sharpe) * 100


@dataclass
class WalkForwardResults:
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


class WalkForwardEngine:
    """Run rolling walk-forward validation using BacktestEngine."""

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

        return results
