"""Unit tests for crypto-specific risk overlays in RiskManager."""

import json

from config.settings import Settings
from src.data.models import Position, Signal, SignalType
from src.risk.manager import RiskManager


def _signal(symbol: str, strength: float = 1.0, metadata: dict | None = None) -> Signal:
    from datetime import datetime, timezone

    return Signal(
        symbol=symbol,
        signal_type=SignalType.LONG,
        strength=strength,
        timestamp=datetime.now(timezone.utc),
        strategy_name="test",
        metadata=metadata or {},
    )


def _position(symbol: str, qty: float, price: float) -> Position:
    return Position(symbol=symbol, qty=qty, avg_entry_price=price, current_price=price)


def _base_settings() -> Settings:
    settings = Settings()
    settings.broker.paper_trading = False
    settings.risk.skip_sector_concentration = True
    settings.risk.max_position_pct = 0.10
    settings.risk.max_portfolio_risk_pct = 0.50
    settings.correlation.threshold = 0.99
    settings.data.symbol_asset_class_map = {"BTCGBP": "CRYPTO", "ETHGBP": "CRYPTO"}
    return settings


def test_crypto_symbol_uses_tighter_max_position_pct_than_equity():
    settings = _base_settings()
    risk = RiskManager(settings)

    equity_order = risk.approve_signal(_signal("HSBA.L"), 100_000.0, 100.0, {})
    crypto_order = risk.approve_signal(_signal("BTCGBP"), 100_000.0, 100.0, {})

    assert equity_order is not None
    assert crypto_order is not None
    assert equity_order.qty == 100.0
    assert crypto_order.qty == 50.0


def test_crypto_symbol_uses_wider_stop_loss_pct():
    settings = _base_settings()
    settings.risk.use_atr_stops = False
    risk = RiskManager(settings)

    equity_order = risk.approve_signal(_signal("HSBA.L"), 100_000.0, 100.0, {})
    crypto_order = risk.approve_signal(_signal("BTCGBP"), 100_000.0, 100.0, {})

    assert equity_order is not None
    assert crypto_order is not None
    assert equity_order.stop_loss == 95.0
    assert crypto_order.stop_loss == 92.0


def test_crypto_total_exposure_limit_rejects_when_projection_exceeds_cap():
    settings = _base_settings()
    settings.crypto_risk.max_portfolio_crypto_pct = 0.15
    settings.risk.max_portfolio_risk_pct = 1.0
    risk = RiskManager(settings)

    open_positions = {
        "BTCGBP": _position("BTCGBP", qty=120.0, price=100.0),
    }

    order = risk.approve_signal(_signal("ETHGBP"), 100_000.0, 100.0, open_positions)

    assert order is None
    rejection = risk.get_last_rejection()
    assert rejection["code"] == "CRYPTO_EXPOSURE_LIMIT"


def test_btcgbp_exists_in_uk_correlation_matrix():
    with open("config/uk_correlations.json", encoding="utf-8") as file:
        matrix = json.load(file)

    assert "BTCGBP" in matrix
    assert "HSBA.L" in matrix["BTCGBP"]
    assert "BTCGBP" in matrix["HSBA.L"]
