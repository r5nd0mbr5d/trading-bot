"""Unit tests for TradingLoopHandler critical control paths."""

from datetime import datetime, timezone

from config.settings import Settings
from src.data.models import Bar, Order, OrderSide, OrderStatus, Signal, SignalType
from src.strategies.base import BaseStrategy
from src.trading.loop import TradingLoopHandler


class DummyStrategy(BaseStrategy):
    """Minimal strategy used for handler tests."""

    def generate_signal(self, symbol: str):
        _ = symbol
        return None


class DummyRisk:
    """Risk manager stub for trading-loop tests."""

    def __init__(self):
        self._rejection = {"code": "", "reason": ""}
        self.recorded_results = []

    def approve_signal(self, signal, portfolio_value, price, positions):
        _ = (signal, portfolio_value, price, positions)
        return None

    def get_last_rejection(self):
        return self._rejection

    def record_trade_result(self, is_profitable: bool):
        self.recorded_results.append(is_profitable)


class DummyBroker:
    """Broker stub for trading-loop tests."""

    def __init__(self):
        self._order_to_return = None

    def get_positions(self):
        return {}

    def get_portfolio_value(self):
        return 100_000.0

    def submit_order(self, order: Order):
        _ = order
        return self._order_to_return

    def get_symbol_currency(self, symbol: str) -> str:
        _ = symbol
        return "GBP"


class DummyTracker:
    """Portfolio tracker stub."""

    def snapshot(self, positions, cash, **kwargs):
        _ = (positions, cash, kwargs)
        return {
            "portfolio_value": 100_000.0,
            "cash": 50_000.0,
            "num_positions": 1,
            "return_pct": 1.0,
        }


class DummyDataQuality:
    """Data quality stub."""

    def __init__(self, reasons=None):
        self._reasons = reasons or []

    def check_bar(self, symbol, bar_timestamp, now_timestamp):
        _ = (symbol, bar_timestamp, now_timestamp)
        return self._reasons


class DummyKillSwitch:
    """Kill switch stub."""

    def __init__(self):
        self.triggered_reasons = []

    def trigger(self, reason: str):
        self.triggered_reasons.append(reason)

    def check_and_raise(self):
        return None


def _build_handler(settings: Settings, risk: DummyRisk, broker: DummyBroker, data_quality: DummyDataQuality):
    audit_events = []

    def enqueue_audit(event_type, payload, **kwargs):
        audit_events.append((event_type, payload, kwargs))

    handler = TradingLoopHandler(
        settings=settings,
        strategy=DummyStrategy(settings),
        risk=risk,
        broker=broker,
        tracker=DummyTracker(),
        data_quality=data_quality,
        kill_switch=DummyKillSwitch(),
        audit=None,
        enqueue_audit=enqueue_audit,
        broker_retry_state={},
    )
    return handler, audit_events


def test_gate_risk_emits_correlation_rejection_audit(monkeypatch):
    settings = Settings()
    risk = DummyRisk()
    risk._rejection = {"code": "CORRELATION_LIMIT", "reason": "high corr"}
    broker = DummyBroker()
    handler, audit_events = _build_handler(settings, risk, broker, DummyDataQuality())

    monkeypatch.setattr(
        "src.trading.loop.run_broker_operation",
        lambda _settings, _name, operation, **_kwargs: operation(),
    )

    signal = Signal(
        symbol="HSBA.L",
        signal_type=SignalType.LONG,
        strength=1.0,
        timestamp=datetime(2024, 1, 2, tzinfo=timezone.utc),
        strategy_name="DummyStrategy",
    )

    order = handler._gate_risk(signal, 100.0)

    assert order is None
    assert any(event[0] == "CORRELATION_LIMIT" for event in audit_events)


def test_check_data_quality_triggers_kill_switch_on_consecutive_stale():
    settings = Settings()
    risk = DummyRisk()
    broker = DummyBroker()
    data_quality = DummyDataQuality(reasons=["stale_data_max_consecutive"])
    handler, audit_events = _build_handler(settings, risk, broker, data_quality)

    bar = Bar(
        symbol="HSBA.L",
        timestamp=datetime(2024, 1, 2, tzinfo=timezone.utc),
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=10_000.0,
    )

    allowed = handler._check_data_quality(bar)

    assert allowed is False
    assert "stale_data_max_consecutive" in handler.kill_switch.triggered_reasons
    event_types = [event[0] for event in audit_events]
    assert "DATA_QUALITY_BLOCK" in event_types
    assert "KILL_SWITCH_TRIGGERED" in event_types


def test_submit_order_emits_filled_audit_with_ibkr_currency(monkeypatch):
    settings = Settings()
    settings.broker.provider = "ibkr"
    settings.broker.commission_per_share = 0.01

    risk = DummyRisk()
    broker = DummyBroker()
    broker._order_to_return = Order(
        symbol="HSBA.L",
        side=OrderSide.BUY,
        qty=10.0,
        status=OrderStatus.FILLED,
        filled_price=101.0,
    )
    handler, audit_events = _build_handler(settings, risk, broker, DummyDataQuality())

    monkeypatch.setattr(
        "src.trading.loop.run_broker_operation",
        lambda _settings, _name, operation, **_kwargs: operation(),
    )

    signal = Signal(
        symbol="HSBA.L",
        signal_type=SignalType.LONG,
        strength=1.0,
        timestamp=datetime(2024, 1, 2, tzinfo=timezone.utc),
        strategy_name="DummyStrategy",
    )
    order = Order(symbol="HSBA.L", side=OrderSide.BUY, qty=10.0)

    handler._submit_order(order, signal, price=100.0)

    filled_events = [event for event in audit_events if event[0] == "ORDER_FILLED"]
    assert len(filled_events) == 1
    assert filled_events[0][1]["currency"] == "GBP"


def test_submit_order_rejected_sell_records_loss(monkeypatch):
    settings = Settings()
    risk = DummyRisk()
    broker = DummyBroker()
    broker._order_to_return = Order(
        symbol="HSBA.L",
        side=OrderSide.SELL,
        qty=5.0,
        status=OrderStatus.REJECTED,
    )
    handler, audit_events = _build_handler(settings, risk, broker, DummyDataQuality())

    monkeypatch.setattr(
        "src.trading.loop.run_broker_operation",
        lambda _settings, _name, operation, **_kwargs: operation(),
    )

    signal = Signal(
        symbol="HSBA.L",
        signal_type=SignalType.CLOSE,
        strength=1.0,
        timestamp=datetime(2024, 1, 2, tzinfo=timezone.utc),
        strategy_name="DummyStrategy",
    )
    order = Order(symbol="HSBA.L", side=OrderSide.SELL, qty=5.0)

    handler._submit_order(order, signal, price=100.0)

    assert any(event[0] == "ORDER_NOT_FILLED" for event in audit_events)
    assert risk.recorded_results == [False]
