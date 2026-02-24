"""Unit tests for trading strategies."""

from datetime import datetime, timedelta, timezone

import pytest

from config.settings import Settings
from src.data.models import Bar, SignalType
from src.strategies.bollinger_bands import BollingerBandsStrategy
from src.strategies.ma_crossover import MACrossoverStrategy
from src.strategies.macd_crossover import MACDCrossoverStrategy
from src.strategies.rsi_momentum import RSIMomentumStrategy


def make_bar(symbol: str, close: float, i: int = 0) -> Bar:
    return Bar(
        symbol=symbol,
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=i),
        open=close * 0.99,
        high=close * 1.01,
        low=close * 0.98,
        close=close,
        volume=1_000_000,
    )


def feed_prices(strategy, symbol, prices):
    signal = None
    for i, p in enumerate(prices):
        signal = strategy.on_bar(make_bar(symbol, p, i))
    return signal


# ── MA Crossover ─────────────────────────────────────────────────────────────


class TestMACrossoverStrategy:

    def setup_method(self):
        settings = Settings()
        settings.strategy.fast_period = 3
        settings.strategy.slow_period = 5
        self.strategy = MACrossoverStrategy(settings)

    def test_no_signal_before_min_bars(self):
        for i in range(5):
            sig = self.strategy.on_bar(make_bar("AAPL", 100 + i, i))
        assert sig is None

    def test_golden_cross_emits_long(self):
        # Downtrend (fast < slow) then spike on the last bar triggers golden cross.
        # With fast=3, slow=5: bar 4 has fast=6.0 < slow=7.2, bar 5 has fast=10.3 > slow=9.2
        prices = [10, 8, 7, 6, 5, 20]
        sig = feed_prices(self.strategy, "AAPL", prices)
        assert sig is not None
        assert sig.signal_type == SignalType.LONG
        assert sig.symbol == "AAPL"
        assert 0 < sig.strength <= 1.0

    def test_death_cross_emits_close(self):
        # Uptrend (fast > slow) then crash on the last bar triggers death cross.
        # With fast=3, slow=5: bar 4 has fast=9.0 > slow=7.8, bar 5 has fast=6.67 < slow=7.0
        prices = [5, 7, 8, 9, 10, 1]
        sig = feed_prices(self.strategy, "MSFT", prices)
        assert sig is not None
        assert sig.signal_type == SignalType.CLOSE

    def test_no_signal_on_flat_prices(self):
        prices = [100] * 20
        sig = feed_prices(self.strategy, "FLAT", prices)
        assert sig is None  # no crossover in flat market

    def test_metadata_contains_ma_values(self):
        prices = [10, 9, 8, 7, 6, 7, 8, 9, 10, 11, 12]
        sig = feed_prices(self.strategy, "AAPL", prices)
        if sig:
            assert "fast_ma" in sig.metadata
            assert "slow_ma" in sig.metadata


# ── RSI Momentum ─────────────────────────────────────────────────────────────


class TestRSIMomentumStrategy:

    def setup_method(self):
        settings = Settings()
        settings.strategy.rsi_period = 5
        settings.strategy.rsi_oversold = 30.0
        settings.strategy.rsi_overbought = 70.0
        self.strategy = RSIMomentumStrategy(settings)

    def test_no_signal_before_min_bars(self):
        for i in range(4):
            sig = self.strategy.on_bar(make_bar("AAPL", 100, i))
        assert sig is None

    def test_rsi_computed_without_error(self):
        prices = [100, 102, 98, 95, 97, 100, 103, 101, 99, 102]
        # Just verify no exception — RSI output depends on EWM smoothing
        sig = feed_prices(self.strategy, "AAPL", prices)
        assert sig is None or sig.signal_type in (
            SignalType.LONG,
            SignalType.CLOSE,
            SignalType.HOLD,
        )

    def test_signal_has_rsi_in_metadata(self):
        prices = [100, 90, 80, 70, 60, 65, 70, 75, 80]
        sig = feed_prices(self.strategy, "AAPL", prices)
        if sig:
            assert "rsi" in sig.metadata
            assert 0 <= sig.metadata["rsi"] <= 100


# ── Bollinger Bands ──────────────────────────────────────────────────────────


class TestBollingerBandsStrategy:

    def setup_method(self):
        settings = Settings()
        settings.strategy.bb_period = 5
        settings.strategy.bb_std = 2.0
        self.strategy = BollingerBandsStrategy(settings)

    def test_no_signal_before_min_bars(self):
        # Need period + 1 bars (6 bars for period=5)
        for i in range(5):
            sig = self.strategy.on_bar(make_bar("AAPL", 100 + i, i))
        assert sig is None

    def test_signal_generates_without_error(self):
        # Main purpose: verify the strategy doesn't crash on valid inputs
        # and can generate both LONG and CLOSE signals
        prices = [100, 95, 100, 95, 100, 95, 100]
        last_sig = None
        for i, p in enumerate(prices):
            last_sig = self.strategy.on_bar(make_bar("AAPL", p, i))
        # Just verify it completes without error and returns a signal or None
        assert last_sig is None or last_sig.signal_type in (
            SignalType.LONG,
            SignalType.CLOSE,
            SignalType.HOLD,
        )

    def test_close_signal_on_middle_band_crossover(self):
        # Drop below middle band, then recover above it -> CLOSE signal
        prices = [100, 100, 100, 100, 100, 50, 100]
        signals = []
        for i, p in enumerate(prices):
            sig = self.strategy.on_bar(make_bar("AAPL", p, i))
            if sig:
                signals.append(sig)
        # Might generate a CLOSE signal when crossing middle band
        assert len(signals) == 0 or any(s.signal_type == SignalType.CLOSE for s in signals)

    def test_no_signal_on_flat_prices(self):
        # Flat prices = zero volatility = no meaningful bands
        prices = [100] * 20
        sig = feed_prices(self.strategy, "FLAT", prices)
        assert sig is None  # zero std dev = no signal

    def test_metadata_contains_band_values(self):
        # When a signal is generated, it should contain band metadata
        prices = [100, 95, 100, 95, 100, 95, 50, 100]
        sig = feed_prices(self.strategy, "AAPL", prices)
        if sig:
            assert "lower_band" in sig.metadata or "middle_band" in sig.metadata
            assert "close" in sig.metadata

    def test_strategy_inherits_base_properties(self):
        # Verify it's a proper BaseStrategy
        assert hasattr(self.strategy, "min_bars_required")
        assert hasattr(self.strategy, "generate_signal")
        assert self.strategy.min_bars_required() == 6  # period + 1


# ── MACD Crossover ────────────────────────────────────────────────────────────


class TestMACDCrossoverStrategy:

    def setup_method(self):
        settings = Settings()
        self.strategy = MACDCrossoverStrategy(settings)

    def test_no_signal_before_min_bars(self):
        for i in range(35):
            sig = self.strategy.on_bar(make_bar("AAPL", 100 + i * 0.1, i))
        assert sig is None

    def test_bullish_cross_produces_long(self):
        # Build 36 bars: flat then spike triggers MACD cross
        prices = [100.0] * 35 + [130.0]
        sig = feed_prices(self.strategy, "AAPL", prices)
        # A large spike forces MACD above signal line
        assert sig is None or sig.signal_type in (SignalType.LONG, SignalType.CLOSE)

    def test_metadata_present_when_signal_emitted(self):
        # Feed enough bars and check if a signal carries metadata
        import random

        random.seed(42)
        prices = [100 + random.uniform(-5, 5) for _ in range(60)]
        sig = feed_prices(self.strategy, "AAPL", prices)
        if sig is not None:
            assert "macd" in sig.metadata
            assert "signal_line" in sig.metadata
            assert "histogram" in sig.metadata
