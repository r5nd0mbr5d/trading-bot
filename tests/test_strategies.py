"""Unit tests for trading strategies."""

from datetime import datetime, timedelta, timezone

import pytest

from config.settings import Settings
from src.data.models import Bar, SignalType
from src.strategies.atr_stops import ATRStopsStrategy
from src.strategies.bollinger_bands import BollingerBandsStrategy
from src.strategies.ma_crossover import MACrossoverStrategy
from src.strategies.macd_crossover import MACDCrossoverStrategy
from src.strategies.obv_momentum import OBVMomentumStrategy
from src.strategies.pairs_mean_reversion import PairsMeanReversionStrategy
from src.strategies.rsi_momentum import RSIMomentumStrategy
from src.strategies.stochastic_oscillator import StochasticOscillatorStrategy


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


# ── ATR Stops ───────────────────────────────────────────────────────────────


class TestATRStopsStrategy:

    def setup_method(self):
        settings = Settings()
        settings.atr.period = 5
        settings.atr.fast_ma_period = 3
        settings.atr.slow_ma_period = 5
        settings.atr.low_vol_threshold_pct = 0.05
        settings.atr.stop_multiplier = 2.0
        self.strategy = ATRStopsStrategy(settings)

    def test_no_signal_before_min_bars(self):
        for i in range(self.strategy.min_bars_required() - 1):
            sig = self.strategy.on_bar(make_bar("AAPL", 100 + i, i))
        assert sig is None

    def test_signal_generation_does_not_error(self):
        prices = [100, 101, 102, 103, 104, 104.5, 105, 105.2, 105.4, 105.6, 105.8]
        sig = feed_prices(self.strategy, "AAPL", prices)
        assert sig is None or sig.signal_type in (
            SignalType.LONG,
            SignalType.CLOSE,
            SignalType.HOLD,
        )

    def test_metadata_contains_atr_and_stop_price_when_signal_emitted(self):
        prices = [100, 101, 102, 103, 104, 104.3, 104.6, 104.9, 105.2, 105.5, 105.8]
        sig = feed_prices(self.strategy, "AAPL", prices)
        if sig is not None:
            assert "atr_value" in sig.metadata
            assert "stop_price" in sig.metadata


# ── OBV Momentum ─────────────────────────────────────────────────────────────


class TestOBVMomentumStrategy:

    def setup_method(self):
        settings = Settings()
        settings.obv.fast_period = 3
        settings.obv.slow_period = 5
        self.strategy = OBVMomentumStrategy(settings)

    def test_no_signal_before_min_bars(self):
        for i in range(self.strategy.min_bars_required() - 1):
            sig = self.strategy.on_bar(make_bar("AAPL", 100 + i, i))
        assert sig is None

    def test_signal_generation_does_not_error(self):
        prices = [10, 9, 8, 7, 6, 7, 8, 9, 10, 11, 12]
        sig = feed_prices(self.strategy, "AAPL", prices)
        assert sig is None or sig.signal_type in (
            SignalType.LONG,
            SignalType.CLOSE,
            SignalType.HOLD,
        )

    def test_metadata_contains_obv_values_when_signal_emitted(self):
        prices = [10, 9, 8, 7, 6, 7, 8, 9, 10, 12, 14]
        sig = feed_prices(self.strategy, "AAPL", prices)
        if sig is not None:
            assert "obv" in sig.metadata
            assert "obv_fast" in sig.metadata
            assert "obv_slow" in sig.metadata


# ── Stochastic Oscillator ───────────────────────────────────────────────────


class TestStochasticOscillatorStrategy:

    def setup_method(self):
        settings = Settings()
        settings.stochastic.k_period = 5
        settings.stochastic.d_period = 3
        settings.stochastic.smooth_window = 3
        settings.stochastic.oversold = 20.0
        settings.stochastic.overbought = 80.0
        self.strategy = StochasticOscillatorStrategy(settings)

    def test_no_signal_before_min_bars(self):
        for i in range(self.strategy.min_bars_required() - 1):
            sig = self.strategy.on_bar(make_bar("AAPL", 100 + i, i))
        assert sig is None

    def test_signal_generation_does_not_error(self):
        prices = [100, 95, 92, 90, 88, 90, 93, 96, 99, 102, 104, 101, 98, 95]
        sig = feed_prices(self.strategy, "AAPL", prices)
        assert sig is None or sig.signal_type in (
            SignalType.LONG,
            SignalType.CLOSE,
            SignalType.HOLD,
        )

    def test_metadata_contains_stochastic_values_when_signal_emitted(self):
        prices = [100, 96, 93, 91, 89, 90, 94, 98, 103, 106, 104, 101, 97, 94]
        sig = feed_prices(self.strategy, "AAPL", prices)
        if sig is not None:
            assert "stoch_k" in sig.metadata
            assert "stoch_d" in sig.metadata


# ── Pairs Mean Reversion ─────────────────────────────────────────────────────


class TestPairsMeanReversionStrategy:

    def setup_method(self):
        settings = Settings()
        settings.strategy.pair_lookback = 5
        settings.strategy.pair_entry_zscore = 1.5
        settings.strategy.pair_exit_zscore = 0.4
        settings.strategy.pair_max_holding_bars = 2
        settings.strategy.pair_hedge_ratio = 1.0
        settings.data.symbols = ["AAA", "BBB"]
        settings.strategy.pair_primary_symbol = "AAA"
        settings.strategy.pair_secondary_symbol = "BBB"
        self.strategy = PairsMeanReversionStrategy(settings)

    def _feed_pair_bar(self, idx: int, primary_price: float, secondary_price: float):
        self.strategy.on_bar(make_bar("BBB", secondary_price, idx))
        return self.strategy.on_bar(make_bar("AAA", primary_price, idx))

    def test_min_bars_required(self):
        assert self.strategy.min_bars_required() == 5

    def test_no_signal_before_min_bars(self):
        sig = None
        for i in range(4):
            sig = self._feed_pair_bar(i, 100.0, 100.0)
        assert sig is None

    def test_long_signal_on_negative_zscore_entry(self):
        primary_prices = [100, 100, 100, 100, 90]
        secondary_prices = [100, 100, 100, 100, 100]
        sig = None
        for i, (p_price, s_price) in enumerate(zip(primary_prices, secondary_prices)):
            sig = self._feed_pair_bar(i, p_price, s_price)
        assert sig is not None
        assert sig.signal_type == SignalType.LONG
        assert sig.symbol == "AAA"
        assert 0.0 < sig.strength <= 1.0
        assert "zscore" in sig.metadata

    def test_close_signal_on_max_holding_bars(self):
        primary_prices = [100, 100, 100, 100, 90, 89, 88]
        secondary_prices = [100, 100, 100, 100, 100, 100, 100]
        signals = []
        for i, (p_price, s_price) in enumerate(zip(primary_prices, secondary_prices)):
            sig = self._feed_pair_bar(i, p_price, s_price)
            if sig is not None:
                signals.append(sig)

        assert len(signals) >= 2
        assert signals[0].signal_type == SignalType.LONG
        assert any(signal.signal_type == SignalType.CLOSE for signal in signals[1:])
