"""Unit tests for the risk manager."""

import json
from datetime import datetime, timezone

import pytest

from config.settings import Settings
from src.data.models import OrderSide, Position, Signal, SignalType
from src.risk.manager import RiskManager


def make_signal(symbol="AAPL", signal_type=SignalType.LONG, strength=1.0):
    return Signal(
        symbol=symbol,
        signal_type=signal_type,
        strength=strength,
        timestamp=datetime.now(timezone.utc),
        strategy_name="test",
    )


def make_position(symbol, qty=10, entry=150.0, current=155.0):
    return Position(symbol=symbol, qty=qty, avg_entry_price=entry, current_price=current)


class TestRiskManager:

    def setup_method(self):
        settings = Settings()
        settings.risk.max_position_pct = 0.10
        settings.risk.max_portfolio_risk_pct = 0.02
        settings.risk.stop_loss_pct = 0.05
        settings.risk.take_profit_pct = 0.15
        settings.risk.max_open_positions = 3
        settings.risk.max_drawdown_pct = 0.20
        settings.initial_capital = 100_000.0
        # Disable paper guardrails in unit tests (only applies to paper trading mode)
        settings.broker.paper_trading = False
        self.risk = RiskManager(settings)

    def test_valid_buy_signal_approved(self):
        order = self.risk.approve_signal(make_signal(), 100_000, 150.0, {})
        assert order is not None
        assert order.side == OrderSide.BUY
        assert order.qty > 0

    def test_position_value_within_cap(self):
        order = self.risk.approve_signal(make_signal(), 100_000, 150.0, {})
        assert order is not None
        assert order.qty * 150.0 <= 100_000 * 0.10 + 0.01  # max_position_pct + rounding

    def test_stop_loss_attached(self):
        order = self.risk.approve_signal(make_signal(), 100_000, 150.0, {})
        assert order is not None
        assert order.stop_loss is not None
        assert order.stop_loss < 150.0

    def test_take_profit_attached(self):
        order = self.risk.approve_signal(make_signal(), 100_000, 150.0, {})
        assert order is not None
        assert order.take_profit is not None
        assert order.take_profit > 150.0

    def test_duplicate_position_rejected(self):
        existing = {"AAPL": make_position("AAPL")}
        order = self.risk.approve_signal(make_signal("AAPL"), 100_000, 155.0, existing)
        assert order is None

    def test_max_positions_blocks_new_trade(self):
        existing = {
            "AAPL": make_position("AAPL"),
            "MSFT": make_position("MSFT"),
            "GOOGL": make_position("GOOGL"),
        }
        order = self.risk.approve_signal(make_signal("TSLA"), 100_000, 200.0, existing)
        assert order is None

    def test_circuit_breaker_triggers_at_threshold(self):
        self.risk._peak_value = 100_000
        # 25% drawdown — exceeds 20% limit
        order = self.risk.approve_signal(make_signal(), 75_000, 150.0, {})
        assert order is None

    def test_circuit_breaker_allows_trade_within_limit(self):
        self.risk._peak_value = 100_000
        # 10% drawdown — within 20% limit
        order = self.risk.approve_signal(make_signal(), 90_000, 150.0, {})
        assert order is not None

    def test_close_signal_sells_existing_position(self):
        existing = {"AAPL": make_position("AAPL", qty=10)}
        order = self.risk.approve_signal(
            make_signal("AAPL", SignalType.CLOSE), 100_000, 155.0, existing
        )
        assert order is not None
        assert order.side == OrderSide.SELL
        assert order.qty == 10

    def test_close_signal_with_no_position_returns_none(self):
        order = self.risk.approve_signal(make_signal("AAPL", SignalType.CLOSE), 100_000, 155.0, {})
        assert order is None

    def test_weak_signal_produces_smaller_position(self):
        order_full = self.risk.approve_signal(make_signal(strength=1.0), 100_000, 150.0, {})
        self.risk._peak_value = 100_000  # reset after circuit breaker state update
        order_weak = self.risk.approve_signal(make_signal(strength=0.2), 100_000, 150.0, {})
        assert order_full is not None and order_weak is not None
        assert order_full.qty > order_weak.qty

    # --- Division-by-zero and edge-case guards ---

    def test_zero_price_returns_no_order(self):
        order = self.risk.approve_signal(make_signal(), 100_000, 0.0, {})
        assert order is None

    def test_negative_price_returns_no_order(self):
        order = self.risk.approve_signal(make_signal(), 100_000, -50.0, {})
        assert order is None

    def test_zero_portfolio_value_returns_no_order(self):
        order = self.risk.approve_signal(make_signal(), 0.0, 150.0, {})
        assert order is None

    def test_negative_portfolio_value_returns_no_order(self):
        order = self.risk.approve_signal(make_signal(), -1.0, 150.0, {})
        assert order is None

    def test_zero_stop_loss_pct_returns_no_order(self):
        self.risk.cfg.stop_loss_pct = 0.0
        order = self.risk.approve_signal(make_signal(), 100_000, 150.0, {})
        assert order is None

    def test_signal_strength_above_one_rejected_at_model_boundary(self):
        with pytest.raises(ValueError, match="Signal.strength"):
            make_signal(strength=5.0)

    def test_signal_strength_below_zero_rejected_at_model_boundary(self):
        with pytest.raises(ValueError, match="Signal.strength"):
            make_signal(strength=-1.0)

    def test_non_finite_inputs_produce_no_order(self):
        order_nan_price = self.risk.approve_signal(make_signal(), 100_000, float("nan"), {})
        self.risk._peak_value = 100_000
        order_inf_portfolio = self.risk.approve_signal(make_signal(), float("inf"), 150.0, {})
        assert order_nan_price is None
        assert order_inf_portfolio is None

    def test_zero_peak_value_does_not_divide_by_zero(self):
        self.risk._peak_value = 0.0
        order = self.risk.approve_signal(make_signal(), 100_000, 150.0, {})
        assert order is not None

    # --- Intraday loss circuit breaker ---

    def test_intraday_circuit_breaker_triggers(self):
        # Set intraday start value high, then drop by more than max_intraday_loss_pct
        self.risk.cfg.max_intraday_loss_pct = 0.02
        # Simulate start of day at 100_000
        self.risk.approve_signal(make_signal(), 100_000, 150.0, {})
        self.risk._peak_value = 100_000
        # Now portfolio drops 3% intraday — should halt
        order = self.risk.approve_signal(make_signal(), 97_000, 150.0, {})
        assert order is None

    def test_intraday_circuit_breaker_resets_on_new_day(self):
        from datetime import datetime, timedelta, timezone

        self.risk.cfg.max_intraday_loss_pct = 0.02
        # Day 1: trigger intraday halt
        day1_signal = Signal(
            symbol="AAPL",
            signal_type=SignalType.LONG,
            strength=1.0,
            timestamp=datetime(2024, 1, 2, 15, 0, tzinfo=timezone.utc),
            strategy_name="test",
        )
        self.risk.approve_signal(day1_signal, 100_000, 150.0, {})
        self.risk._peak_value = 100_000
        halted = self.risk.approve_signal(day1_signal, 97_000, 150.0, {})
        assert halted is None
        # Day 2: fresh start
        day2_signal = Signal(
            symbol="AAPL",
            signal_type=SignalType.LONG,
            strength=1.0,
            timestamp=datetime(2024, 1, 3, 15, 0, tzinfo=timezone.utc),
            strategy_name="test",
        )
        order = self.risk.approve_signal(day2_signal, 97_000, 150.0, {})
        assert order is not None

    # --- Consecutive loss circuit breaker ---

    def test_consecutive_loss_circuit_breaker_triggers(self):
        self.risk.cfg.consecutive_loss_limit = 3
        self.risk.record_trade_result(False)
        self.risk.record_trade_result(False)
        self.risk.record_trade_result(False)
        order = self.risk.approve_signal(make_signal(), 100_000, 150.0, {})
        assert order is None

    def test_consecutive_loss_resets_on_win(self):
        self.risk.cfg.consecutive_loss_limit = 3
        self.risk.record_trade_result(False)
        self.risk.record_trade_result(False)
        self.risk.record_trade_result(True)  # win resets counter
        order = self.risk.approve_signal(make_signal(), 100_000, 150.0, {})
        assert order is not None

    def test_consecutive_loss_counter_increments(self):
        self.risk.record_trade_result(False)
        self.risk.record_trade_result(False)
        assert self.risk._consecutive_losses == 2

    def test_record_win_resets_counter_to_zero(self):
        self.risk.record_trade_result(False)
        self.risk.record_trade_result(False)
        self.risk.record_trade_result(True)
        assert self.risk._consecutive_losses == 0

    def test_sector_concentration_blocks_excess(self, tmp_path):
        settings = Settings()
        settings.broker.paper_trading = False
        settings.risk.max_sector_concentration_pct = 0.40
        settings.risk.sector_map_path = str(tmp_path / "baskets.json")

        basket_payload = {
            "baskets": {
                "energy": {
                    "symbols": ["ENG1", "ENG2", "ENG3"],
                    "symbol_details": {
                        "ENG1": {"sector": "Energy"},
                        "ENG2": {"sector": "Energy"},
                        "ENG3": {"sector": "Energy"},
                    },
                }
            }
        }
        (tmp_path / "baskets.json").write_text(
            json.dumps(basket_payload),
            encoding="utf-8",
        )

        risk = RiskManager(settings)
        open_positions = {
            "ENG1": make_position("ENG1", qty=175, entry=100.0, current=100.0),
            "ENG2": make_position("ENG2", qty=175, entry=100.0, current=100.0),
        }
        order = risk.approve_signal(make_signal("ENG3"), 100_000, 100.0, open_positions)
        assert order is None
        rejection = risk.get_last_rejection()
        assert rejection["code"] == "SECTOR_CONCENTRATION_REJECTED"
        assert "limit" in rejection["reason"]

    def test_sector_concentration_allows_within_limit(self, tmp_path):
        settings = Settings()
        settings.broker.paper_trading = False
        settings.risk.max_sector_concentration_pct = 0.40
        settings.risk.sector_map_path = str(tmp_path / "baskets.json")

        basket_payload = {
            "baskets": {
                "energy": {
                    "symbols": ["ENG1", "ENG2", "ENG3"],
                    "symbol_details": {
                        "ENG1": {"sector": "Energy"},
                        "ENG2": {"sector": "Energy"},
                        "ENG3": {"sector": "Energy"},
                    },
                }
            }
        }
        (tmp_path / "baskets.json").write_text(
            json.dumps(basket_payload),
            encoding="utf-8",
        )

        risk = RiskManager(settings)
        open_positions = {
            "ENG1": make_position("ENG1", qty=150, entry=100.0, current=100.0),
            "ENG2": make_position("ENG2", qty=150, entry=100.0, current=100.0),
        }
        order = risk.approve_signal(make_signal("ENG3"), 100_000, 100.0, open_positions)
        assert order is not None
