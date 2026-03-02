"""Regression tests for slippage and commission modelling."""

from datetime import datetime, timedelta, timezone

import pandas as pd

from backtest.engine import BacktestEngine
from config.settings import Settings
from src.data.models import Signal, SignalType
from src.execution.slippage import SlippageModel
from src.strategies.base import BaseStrategy


class EntryExitStrategy(BaseStrategy):
    """Emit one long entry then one close signal later."""

    def __init__(self, settings: Settings, entry_index: int = 0, exit_index: int = 12):
        super().__init__(settings)
        self._entry_index = entry_index
        self._exit_index = exit_index

    def generate_signal(self, symbol: str):
        history = self._bar_history.get(symbol, [])
        idx = len(history) - 1
        bar = history[-1]

        if idx == self._entry_index:
            return Signal(
                symbol=symbol,
                signal_type=SignalType.LONG,
                strength=1.0,
                timestamp=bar.timestamp,
                strategy_name=self.name,
            )

        if idx == self._exit_index:
            return Signal(
                symbol=symbol,
                signal_type=SignalType.CLOSE,
                strength=1.0,
                timestamp=bar.timestamp,
                strategy_name=self.name,
            )

        return None


def _sample_frame(
    days: int = 20, base_price: float = 100.0, volume: float = 5_000.0
) -> pd.DataFrame:
    rows = []
    timestamps = [
        datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=i) for i in range(days)
    ]
    for i, ts in enumerate(timestamps):
        open_price = base_price + i * 0.8
        rows.append(
            {
                "timestamp": ts,
                "open": open_price,
                "high": open_price + 1.0,
                "low": open_price - 1.0,
                "close": open_price + 0.4,
                "volume": volume,
            }
        )
    frame = pd.DataFrame(rows).set_index("timestamp")
    return frame


def test_slippage_model_increases_cost_with_order_size_ratio():
    settings = Settings()
    model = SlippageModel(settings.slippage)

    small = model.estimate_slippage_pct(order_size=100, average_daily_volume=100_000)
    large = model.estimate_slippage_pct(order_size=5_000, average_daily_volume=100_000)

    assert large > small


def test_crypto_slippage_preset_uses_zero_commission_floor():
    settings = Settings()
    settings.slippage.preset = "crypto"
    settings.slippage.commission_rate = 0.001
    settings.slippage.commission_min = 1.70

    model = SlippageModel(settings.slippage)
    commission = model.estimate_commission(order_size=0.01, fill_price=100.0)

    assert commission < 1.70


def test_higher_slippage_preset_reduces_backtest_return(monkeypatch):
    start = "2024-01-01"
    end = "2024-01-20"

    optimistic_settings = Settings()
    optimistic_settings.broker.paper_trading = False
    optimistic_settings.data.symbols = ["HSBA.L"]
    optimistic_settings.risk.skip_sector_concentration = True
    optimistic_settings.risk.max_position_pct = 0.95
    optimistic_settings.risk.max_portfolio_risk_pct = 0.2
    optimistic_settings.slippage.preset = "optimistic"

    pessimistic_settings = Settings()
    pessimistic_settings.broker.paper_trading = False
    pessimistic_settings.data.symbols = ["HSBA.L"]
    pessimistic_settings.risk.skip_sector_concentration = True
    pessimistic_settings.risk.max_position_pct = 0.95
    pessimistic_settings.risk.max_portfolio_risk_pct = 0.2
    pessimistic_settings.slippage.preset = "pessimistic"

    optimistic_engine = BacktestEngine(optimistic_settings, EntryExitStrategy(optimistic_settings))
    pessimistic_engine = BacktestEngine(
        pessimistic_settings, EntryExitStrategy(pessimistic_settings)
    )

    frame = _sample_frame()

    def fake_fetch(_symbol, **_kwargs):
        return frame

    monkeypatch.setattr(optimistic_engine.feed, "fetch_historical", fake_fetch)
    monkeypatch.setattr(pessimistic_engine.feed, "fetch_historical", fake_fetch)

    optimistic_results = optimistic_engine.run(start, end)
    pessimistic_results = pessimistic_engine.run(start, end)

    assert optimistic_results.total_return_pct > pessimistic_results.total_return_pct
