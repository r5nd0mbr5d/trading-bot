"""Unit tests for trading loop extraction and stream-event handlers."""

from datetime import datetime, timezone

from config.settings import Settings
from src.data.models import Bar
from src.trading.loop import TradingLoopHandler
from src.trading.stream_events import (
    build_stream_error_handler,
    build_stream_heartbeat_handler,
)


class _DummyStrategy:
    def __init__(self):
        self.bars = []

    def on_bar(self, bar):
        self.bars.append(bar)
        return None

    def min_bars_required(self):
        return 1


class _DummyRisk:
    def update_portfolio_return(self, _value):
        return None

    def approve_signal(self, *_args, **_kwargs):
        return None

    def get_last_rejection(self):
        return {}


class _DummyBroker:
    def get_portfolio_value(self):
        return 100000.0


class _DummyTracker:
    def snapshot(self, *_args, **_kwargs):
        return {
            "portfolio_value": 100000.0,
            "cash": 100000.0,
            "num_positions": 0,
            "return_pct": 0.0,
        }


class _DummyDataQuality:
    def __init__(self, reasons=None):
        self._reasons = reasons or []

    def check_bar(self, *_args, **_kwargs):
        return self._reasons


class _DummyKillSwitch:
    def __init__(self):
        self.triggered = []

    def trigger(self, reason):
        self.triggered.append(reason)

    def check_and_raise(self):
        return None


class _DummyFeed:
    def fetch_historical(self, _symbol, period="5d", interval="1m"):
        return {"period": period, "interval": interval}

    def to_bars(self, symbol, _df):
        return [
            Bar(
                symbol=symbol,
                timestamp=datetime.now(timezone.utc),
                open=1.0,
                high=1.1,
                low=0.9,
                close=1.0,
                volume=100,
            )
        ]


def _build_handler(*, dq_reasons=None, enqueue_events=None):
    settings = Settings()
    settings.enforce_market_hours = False
    settings.data_quality.enable_stale_check = True

    strategy = _DummyStrategy()
    risk = _DummyRisk()
    broker = _DummyBroker()
    tracker = _DummyTracker()
    data_quality = _DummyDataQuality(dq_reasons)
    kill_switch = _DummyKillSwitch()

    events = enqueue_events if enqueue_events is not None else []

    def enqueue_audit(event_type, payload, **kwargs):
        events.append({"event": event_type, "payload": payload, "kwargs": kwargs})

    handler = TradingLoopHandler(
        settings=settings,
        strategy=strategy,
        risk=risk,
        broker=broker,
        tracker=tracker,
        data_quality=data_quality,
        kill_switch=kill_switch,
        audit=None,
        enqueue_audit=enqueue_audit,
        broker_retry_state={"consecutive_failures": 0},
    )
    return handler, strategy, kill_switch, events


def test_prewarm_strategy_feeds_bars_to_strategy():
    handler, strategy, _kill_switch, _events = _build_handler()
    handler.settings.data.symbols = ["AAPL", "MSFT"]

    handler._prewarm_strategy(_DummyFeed())

    assert len(strategy.bars) == 2


def test_initialize_portfolio_value_sets_initial_value(monkeypatch):
    handler, _strategy, _kill_switch, _events = _build_handler()

    monkeypatch.setattr("src.trading.loop.run_broker_operation", lambda *args, **kwargs: 123456.78)
    handler.initialize_portfolio_value()

    assert handler.prev_portfolio_value == 123456.78


def test_on_bar_blocks_on_data_quality_and_triggers_kill_switch():
    handler, _strategy, kill_switch, events = _build_handler(
        dq_reasons=["stale_data_max_consecutive"]
    )
    bar = Bar(
        symbol="AAPL",
        timestamp=datetime.now(timezone.utc),
        open=1.0,
        high=1.1,
        low=0.9,
        close=1.0,
        volume=100,
    )

    handler.on_bar(bar)

    assert "stale_data_max_consecutive" in kill_switch.triggered
    assert any(item["event"] == "DATA_QUALITY_BLOCK" for item in events)
    assert any(item["event"] == "KILL_SWITCH_TRIGGERED" for item in events)


def test_stream_event_builders_emit_expected_audit_events():
    events = []

    def enqueue_audit(event_type, payload, **kwargs):
        events.append({"event": event_type, "payload": payload, "kwargs": kwargs})

    kill_switch = _DummyKillSwitch()
    heartbeat = build_stream_heartbeat_handler(enqueue_audit, "ma_crossover")
    err_handler = build_stream_error_handler(enqueue_audit, "ma_crossover", kill_switch)

    heartbeat({"event": "STREAM_HEARTBEAT", "cycle": 1})
    err_handler({"event": "STREAM_FAILURE_LIMIT_REACHED", "consecutive_failure_cycles": 3})

    assert events[0]["event"] == "STREAM_HEARTBEAT"
    assert events[1]["event"] == "STREAM_FAILURE_LIMIT_REACHED"
    assert kill_switch.triggered
