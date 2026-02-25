"""Unit tests for asset-class metadata and crypto session bypass logic."""

from datetime import datetime, timezone

from config.settings import PaperGuardrailsConfig, Settings
from src.data.models import Bar
from src.risk.paper_guardrails import PaperGuardrails
from src.trading.loop import TradingLoopHandler


class _DummyStrategy:
    def __init__(self):
        self.bar_count = 0

    def on_bar(self, bar):
        self.bar_count += 1
        _ = bar
        return None

    def min_bars_required(self):
        return 1


class _DummyRisk:
    def update_portfolio_return(self, _value):
        return None


class _DummyBroker:
    def get_portfolio_value(self):
        return 100000.0

    def get_positions(self):
        return {}

    def get_cash(self):
        return 100000.0

    def get_account_base_currency(self):
        return "GBP"

    def get_symbol_currency(self, _symbol):
        return "GBP"


class _DummyTracker:
    def snapshot(self, *_args, **_kwargs):
        return {
            "portfolio_value": 100000.0,
            "cash": 100000.0,
            "num_positions": 0,
            "return_pct": 0.0,
        }


class _DummyDataQuality:
    def check_bar(self, *_args, **_kwargs):
        return []


class _DummyKillSwitch:
    def trigger(self, _reason):
        return None

    def check_and_raise(self):
        return None


def _build_handler(settings: Settings):
    strategy = _DummyStrategy()

    def _enqueue_audit(_event_type, _payload, **_kwargs):
        return None

    handler = TradingLoopHandler(
        settings=settings,
        strategy=strategy,
        risk=_DummyRisk(),
        broker=_DummyBroker(),
        tracker=_DummyTracker(),
        data_quality=_DummyDataQuality(),
        kill_switch=_DummyKillSwitch(),
        audit=None,
        enqueue_audit=_enqueue_audit,
        broker_retry_state={"consecutive_failures": 0},
    )
    return handler, strategy


def test_settings_is_crypto_returns_true_for_known_crypto_symbol():
    settings = Settings()

    assert settings.is_crypto("BTCGBP") is True
    assert settings.is_crypto("btc-gbp") is True
    assert settings.is_crypto("BTC/GBP") is True


def test_settings_is_crypto_defaults_unknown_to_equity():
    settings = Settings()

    assert settings.is_crypto("HSBA.L") is False
    assert settings.is_crypto("UNKNOWN") is False


def test_paper_guardrails_crypto_symbol_bypasses_session_window():
    cfg = PaperGuardrailsConfig(
        session_start_hour=8,
        session_end_hour=16,
        session_timezone="UTC",
        skip_session_window=False,
        skip_session_window_for_crypto=True,
    )
    guardrails = PaperGuardrails(cfg)
    guardrails._now_utc = lambda: datetime(2026, 2, 23, 2, 0, 0, tzinfo=timezone.utc)

    reason = guardrails.check_session_window(symbol="BTCGBP", is_crypto=True)

    assert reason == ""


def test_paper_guardrails_equity_symbol_still_respects_session_window():
    cfg = PaperGuardrailsConfig(
        session_start_hour=8,
        session_end_hour=16,
        session_timezone="UTC",
        skip_session_window=False,
        skip_session_window_for_crypto=True,
    )
    guardrails = PaperGuardrails(cfg)
    guardrails._now_utc = lambda: datetime(2026, 2, 23, 2, 0, 0, tzinfo=timezone.utc)

    reason = guardrails.check_session_window(symbol="HSBA.L", is_crypto=False)

    assert "outside_session_window" in reason


def test_trading_loop_market_hours_bypass_for_crypto_symbol():
    settings = Settings()
    settings.enforce_market_hours = True
    settings.data.symbol_asset_class_map = {"BTCGBP": "CRYPTO"}

    handler, strategy = _build_handler(settings)
    weekend_bar = Bar(
        symbol="BTCGBP",
        timestamp=datetime(2026, 2, 22, 12, 0, 0, tzinfo=timezone.utc),
        open=100000.0,
        high=100500.0,
        low=99500.0,
        close=100100.0,
        volume=10.0,
    )

    handler.on_bar(weekend_bar)

    assert strategy.bar_count == 1


def test_trading_loop_market_hours_still_blocks_equity_symbol():
    settings = Settings()
    settings.enforce_market_hours = True
    settings.data.symbol_asset_class_map = {"BTCGBP": "CRYPTO"}

    handler, strategy = _build_handler(settings)
    weekend_bar = Bar(
        symbol="HSBA.L",
        timestamp=datetime(2026, 2, 22, 12, 0, 0, tzinfo=timezone.utc),
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=1000.0,
    )

    handler.on_bar(weekend_bar)

    assert strategy.bar_count == 0
