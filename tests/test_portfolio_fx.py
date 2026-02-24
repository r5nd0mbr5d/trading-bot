"""Unit tests for FX-normalized portfolio snapshots."""

from src.data.models import Position
from src.portfolio.tracker import PortfolioTracker


def test_snapshot_uses_base_currency_conversion_for_positions_and_cash():
    tracker = PortfolioTracker(initial_capital=100_000.0)
    positions = {
        "AAPL": Position(symbol="AAPL", qty=10, avg_entry_price=100.0, current_price=110.0),
        "HSBA.L": Position(symbol="HSBA.L", qty=10, avg_entry_price=90.0, current_price=100.0),
    }

    snap = tracker.snapshot(
        positions,
        cash=1_000.0,
        base_currency="GBP",
        symbol_currencies={"AAPL": "USD", "HSBA.L": "GBP"},
        cash_currency="USD",
        fx_rates={"USD_GBP": 0.8},
    )

    # AAPL market value: 10*110=1100 USD -> 880 GBP
    # HSBA market value: 10*100=1000 GBP
    # cash: 1000 USD -> 800 GBP
    assert snap["base_currency"] == "GBP"
    assert snap["market_value"] == 1880.0
    assert snap["cash"] == 800.0
    assert snap["portfolio_value"] == 2680.0


def test_snapshot_uses_inverse_rate_when_only_reverse_pair_available():
    tracker = PortfolioTracker(initial_capital=10_000.0)
    positions = {
        "AAPL": Position(symbol="AAPL", qty=1, avg_entry_price=100.0, current_price=120.0),
    }

    snap = tracker.snapshot(
        positions,
        cash=0.0,
        base_currency="GBP",
        symbol_currencies={"AAPL": "USD"},
        fx_rates={"GBP_USD": 1.25},
    )

    # inverse of 1.25 is 0.8, so 120 USD -> 96 GBP
    assert snap["portfolio_value"] == 96.0
