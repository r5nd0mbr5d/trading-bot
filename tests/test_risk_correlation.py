"""Unit tests for correlation-based concentration limits in RiskManager."""

from datetime import datetime, timezone
import json

from config.settings import Settings
from src.data.models import Position, Signal, SignalType
from src.risk.manager import RiskManager


def _signal(symbol: str, strength: float = 1.0) -> Signal:
    return Signal(
        symbol=symbol,
        signal_type=SignalType.LONG,
        strength=strength,
        timestamp=datetime.now(timezone.utc),
        strategy_name="test",
    )


def _position(symbol: str, qty: float = 100.0, price: float = 100.0) -> Position:
    return Position(symbol=symbol, qty=qty, avg_entry_price=price, current_price=price)


def _write_corr_matrix(path: str) -> None:
    matrix = {
        "HSBA.L": {"BARC.L": 0.82, "BP.L": 0.30},
        "BARC.L": {"HSBA.L": 0.82, "BP.L": 0.25},
        "BP.L": {"HSBA.L": 0.30, "BARC.L": 0.25},
    }
    with open(path, "w", encoding="utf-8") as file:
        json.dump(matrix, file)


def test_correlation_limit_rejects_highly_correlated_signal(tmp_path):
    settings = Settings()
    settings.broker.paper_trading = False
    settings.correlation.matrix_path = str(tmp_path / "corr.json")
    settings.correlation.threshold = 0.7
    settings.correlation.mode = "reject"
    _write_corr_matrix(settings.correlation.matrix_path)

    risk = RiskManager(settings)
    open_positions = {"BARC.L": _position("BARC.L")}

    order = risk.approve_signal(_signal("HSBA.L"), 100_000.0, 100.0, open_positions)

    assert order is None
    rejection = risk.get_last_rejection()
    assert rejection["code"] == "CORRELATION_LIMIT"
    assert "exceeds threshold" in rejection["reason"]


def test_correlation_limit_allows_low_correlation_signal(tmp_path):
    settings = Settings()
    settings.broker.paper_trading = False
    settings.correlation.matrix_path = str(tmp_path / "corr.json")
    settings.correlation.threshold = 0.7
    settings.correlation.mode = "reject"
    _write_corr_matrix(settings.correlation.matrix_path)

    risk = RiskManager(settings)
    open_positions = {"BARC.L": _position("BARC.L")}

    order = risk.approve_signal(_signal("BP.L"), 100_000.0, 100.0, open_positions)

    assert order is not None


def test_correlation_limit_scales_position_when_mode_scale(tmp_path):
    settings = Settings()
    settings.broker.paper_trading = False
    settings.risk.max_position_pct = 1.0
    settings.risk.skip_sector_concentration = True
    settings.correlation.matrix_path = str(tmp_path / "corr.json")
    settings.correlation.threshold = 0.7
    settings.correlation.mode = "scale"
    _write_corr_matrix(settings.correlation.matrix_path)

    risk_scaled = RiskManager(settings)
    open_positions = {"BARC.L": _position("BARC.L")}

    scaled_order = risk_scaled.approve_signal(_signal("HSBA.L"), 100_000.0, 100.0, open_positions)

    baseline_settings = Settings()
    baseline_settings.broker.paper_trading = False
    baseline_settings.risk.max_position_pct = 1.0
    baseline_settings.risk.skip_sector_concentration = True
    baseline_settings.correlation.matrix_path = str(tmp_path / "corr.json")
    baseline_settings.correlation.threshold = 0.95
    baseline_settings.correlation.mode = "reject"
    _write_corr_matrix(baseline_settings.correlation.matrix_path)
    baseline_risk = RiskManager(baseline_settings)

    baseline_order = baseline_risk.approve_signal(
        _signal("HSBA.L"), 100_000.0, 100.0, open_positions
    )

    assert scaled_order is not None
    assert baseline_order is not None
    assert scaled_order.qty < baseline_order.qty
