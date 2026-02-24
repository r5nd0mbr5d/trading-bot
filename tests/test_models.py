"""Tests for core data model invariants and validation rules."""

from datetime import datetime, timezone

import pytest

from src.data.models import Bar, Order, OrderSide, Signal, SignalType


def test_signal_strength_accepts_valid_bounds() -> None:
    signal_low = Signal(
        symbol="AAPL",
        signal_type=SignalType.LONG,
        strength=0.0,
        timestamp=datetime.now(timezone.utc),
        strategy_name="test",
    )
    signal_high = Signal(
        symbol="AAPL",
        signal_type=SignalType.LONG,
        strength=1.0,
        timestamp=datetime.now(timezone.utc),
        strategy_name="test",
    )

    assert signal_low.strength == 0.0
    assert signal_high.strength == 1.0


@pytest.mark.parametrize("invalid_strength", [-0.1, 1.1])
def test_signal_strength_rejects_out_of_range(invalid_strength: float) -> None:
    with pytest.raises(ValueError, match="Signal.strength"):
        Signal(
            symbol="AAPL",
            signal_type=SignalType.LONG,
            strength=invalid_strength,
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
        )


def test_bar_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="Bar.timestamp"):
        Bar(
            symbol="AAPL",
            timestamp=datetime.now(),
            open=1.0,
            high=1.2,
            low=0.9,
            close=1.1,
            volume=1000,
        )


def test_signal_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="Signal.timestamp"):
        Signal(
            symbol="AAPL",
            signal_type=SignalType.LONG,
            strength=0.5,
            timestamp=datetime.now(),
            strategy_name="test",
        )


def test_order_rejects_naive_filled_at_timestamp() -> None:
    with pytest.raises(ValueError, match="Order.filled_at"):
        Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            qty=1.0,
            filled_at=datetime.now(),
        )


def test_models_accept_timezone_aware_timestamps() -> None:
    bar = Bar(
        symbol="AAPL",
        timestamp=datetime.now(timezone.utc),
        open=1.0,
        high=1.2,
        low=0.9,
        close=1.1,
        volume=1000,
    )
    signal = Signal(
        symbol="AAPL",
        signal_type=SignalType.LONG,
        strength=0.5,
        timestamp=datetime.now(timezone.utc),
        strategy_name="test",
    )
    order = Order(
        symbol="AAPL",
        side=OrderSide.BUY,
        qty=1.0,
        filled_at=datetime.now(timezone.utc),
    )

    assert bar.symbol == "AAPL"
    assert signal.symbol == "AAPL"
    assert order.symbol == "AAPL"
