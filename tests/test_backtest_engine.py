"""Backtest engine regression tests."""

from datetime import datetime, timezone

import pandas as pd

from backtest.engine import BacktestEngine
from config.settings import Settings
from src.data.models import Signal, SignalType
from src.strategies.base import BaseStrategy


class OneShotLongStrategy(BaseStrategy):
    def __init__(self, settings: Settings, target_symbol: str):
        super().__init__(settings)
        self.target_symbol = target_symbol

    def generate_signal(self, symbol: str):
        if symbol != self.target_symbol:
            return None
        history = self._bar_history.get(symbol, [])
        if len(history) == 1:
            bar = history[-1]
            return Signal(
                symbol=symbol,
                signal_type=SignalType.LONG,
                strength=1.0,
                timestamp=bar.timestamp,
                strategy_name=self.name,
            )
        return None


def _frame(rows):
    idx = [r[0] for r in rows]
    return pd.DataFrame(
        {
            "open": [r[1] for r in rows],
            "high": [r[2] for r in rows],
            "low": [r[3] for r in rows],
            "close": [r[4] for r in rows],
            "volume": [r[5] for r in rows],
        },
        index=pd.DatetimeIndex(idx),
    )


def test_pending_orders_carry_to_next_available_symbol_open(monkeypatch):
    settings = Settings()
    settings.broker.paper_trading = False
    settings.data.symbols = ["AAA", "BBB"]

    strategy = OneShotLongStrategy(settings, target_symbol="AAA")
    engine = BacktestEngine(settings, strategy)

    a_rows = [
        (datetime(2024, 1, 1, tzinfo=timezone.utc), 100.0, 101.0, 99.0, 100.5, 1000),
        (datetime(2024, 1, 3, tzinfo=timezone.utc), 110.0, 111.0, 109.0, 110.5, 1000),
    ]
    b_rows = [
        (datetime(2024, 1, 1, tzinfo=timezone.utc), 50.0, 51.0, 49.0, 50.5, 1000),
        (datetime(2024, 1, 2, tzinfo=timezone.utc), 51.0, 52.0, 50.0, 51.5, 1000),
        (datetime(2024, 1, 3, tzinfo=timezone.utc), 52.0, 53.0, 51.0, 52.5, 1000),
    ]

    def fake_fetch(symbol, **kwargs):
        if symbol == "AAA":
            return _frame(a_rows)
        return _frame(b_rows)

    monkeypatch.setattr(engine.feed, "fetch_historical", fake_fetch)

    results = engine.run("2024-01-01", "2024-01-03")

    buy_trades = [t for t in results.trades if t["symbol"] == "AAA" and t["side"] == "buy"]
    assert len(buy_trades) == 1
    assert str(buy_trades[0]["date"]).startswith("2024-01-03")
