"""Integration tests for broker reconciliation with mocked brokers."""

from unittest.mock import MagicMock

from config.settings import ReconciliationConfig
from src.audit.broker_reconciliation import BrokerReconciler
from src.data.models import Position
from src.execution.broker import PaperBroker


class TestReconciliationWithMockedBroker:
    """Integration tests with mocked broker."""

    def test_reconcile_with_paper_broker_no_differ(self):
        """PaperBroker with matching positions should pass reconciliation."""
        config = ReconciliationConfig()
        broker = PaperBroker(100_000.0)

        # Set up positions by manually modifying broker state
        # (simulating a previous order fill)
        broker._positions = {"AAPL": Position("AAPL", 100, 150.0, 151.0)}
        broker._current_prices = {"AAPL": 151.0}
        # After buying 100 shares at 151: cash = 100,000 - (100 * 151) = 84,900
        broker._cash = 84_900.0

        reconciler = BrokerReconciler(broker, config)

        # Get broker state
        broker_pos = broker.get_positions()
        broker_cash = broker.get_cash()  # 84,900
        broker_value = broker.get_portfolio_value()  # 84,900 + (100 * 151) = 100,000 (approx)

        # Internal state matches
        internal_pos = {"AAPL": Position("AAPL", 100, 150.0, 151.0)}
        internal_cash = 84_900.0
        internal_value = 84_900.0 + 15_100.0  # cash + market_value

        result = reconciler.reconcile(
            broker_pos, internal_pos, broker_cash, internal_cash, broker_value, internal_value
        )
        assert result.passed is True

    def test_reconcile_detects_broker_position_mismatch(self):
        """Reconciliation should detect when broker has different positions."""
        config = ReconciliationConfig(position_tolerance_shares=1.0)
        broker = PaperBroker(100_000.0)

        # Broker has 150 shares
        broker._positions = {"AAPL": Position("AAPL", 150, 150.0, 151.0)}
        broker._current_prices = {"AAPL": 151.0}

        reconciler = BrokerReconciler(broker, config)

        broker_pos = broker.get_positions()
        broker_cash = broker.get_cash()
        broker_value = broker.get_portfolio_value()

        # Internal only has 100 shares
        internal_pos = {"AAPL": Position("AAPL", 100, 150.0, 151.0)}
        internal_cash = 84_900.0  # Calculated for 100 shares
        internal_value = 84_900.0 + 15_100.0

        result = reconciler.reconcile(
            broker_pos, internal_pos, broker_cash, internal_cash, broker_value, internal_value
        )
        assert result.passed is False
        assert len(result.position_diffs) == 1
        assert result.position_diffs[0].broker_qty == 150
        assert result.position_diffs[0].internal_qty == 100

    def test_reconcile_detects_cash_mismatch(self):
        """Reconciliation should detect cash mismatches."""
        config = ReconciliationConfig(cash_tolerance_dollars=0.01)

        # Mock broker
        mock_broker = MagicMock()
        mock_broker.get_positions.return_value = {}
        mock_broker.get_cash.return_value = 9999.5  # Broker cash
        mock_broker.get_portfolio_value.return_value = 9999.5

        reconciler = BrokerReconciler(mock_broker, config)

        # Reconcile with internal state that differs
        result = reconciler.reconcile(
            {},  # broker positions
            {},  # internal positions
            9999.5,  # broker_cash
            10000.0,  # internal_cash (different)
            9999.5,  # broker_value
            10000.0,  # internal_value
        )
        assert result.passed is False
        assert result.cash_diff is not None
        assert len(result.reasons) >= 1

    def test_reconcile_detects_value_mismatch(self):
        """Reconciliation should detect portfolio value mismatches."""
        config = ReconciliationConfig(value_tolerance_pct=0.5)

        mock_broker = MagicMock()
        mock_broker.get_positions.return_value = {}
        mock_broker.get_cash.return_value = 100_000.0
        mock_broker.get_portfolio_value.return_value = 100_000.0

        reconciler = BrokerReconciler(mock_broker, config)

        # 2% mismatch exceeds 0.5% tolerance
        result = reconciler.reconcile(
            {},  # broker positions
            {},  # internal positions
            100_000.0,  # broker_cash
            100_000.0,  # internal_cash
            102_000.0,  # broker_value (2% higher)
            100_000.0,  # internal_value
        )
        assert result.passed is False
        assert result.value_diff_pct is not None
        assert abs(result.value_diff_pct - 2.0) < 0.1

    def test_reconcile_with_multiple_position_mismatches(self):
        """Reconciliation should detect mismatches in multiple positions."""
        config = ReconciliationConfig(position_tolerance_shares=1.0)
        reconciler = BrokerReconciler(PaperBroker(), config)

        # Broker has different quantities for multiple symbols
        broker_pos = {
            "AAPL": Position("AAPL", 115, 150.0, 151.0),
            "MSFT": Position("MSFT", 55, 300.0, 305.0),
            "GOOGL": Position("GOOGL", 10, 2800.0, 2810.0),
        }

        # Internal has different quantities
        internal_pos = {
            "AAPL": Position("AAPL", 100, 150.0, 151.0),
            "MSFT": Position("MSFT", 50, 300.0, 305.0),
            "GOOGL": Position("GOOGL", 10, 2800.0, 2810.0),  # Matching
        }

        result = reconciler.reconcile(
            broker_pos, internal_pos, 50000.0, 50000.0, 500_000.0, 500_000.0
        )
        assert result.passed is False
        assert len(result.position_diffs) == 2  # AAPL and MSFT mismatch
        assert any(d.symbol == "AAPL" for d in result.position_diffs)
        assert any(d.symbol == "MSFT" for d in result.position_diffs)
        assert not any(d.symbol == "GOOGL" for d in result.position_diffs)

    def test_interval_driven_reconciliation(self):
        """Reconciliation interval based on fill count."""
        config = ReconciliationConfig(enabled=True, reconcile_every_n_fills=5)
        reconciler = BrokerReconciler(PaperBroker(), config)

        # Initially should not reconcile
        assert reconciler.should_reconcile_now() is False

        # Record 4 fills
        for _ in range(4):
            reconciler.record_fill()
        assert reconciler.should_reconcile_now() is False

        # Record 5th fill
        reconciler.record_fill()
        assert reconciler.should_reconcile_now() is True

        # Reset
        reconciler.reset_counter()
        assert reconciler.fill_count == 0
        assert reconciler.should_reconcile_now() is False

    def test_tolerance_prevents_false_positives(self):
        """Tight tolerances should catch reasonable slippage/fees."""
        config = ReconciliationConfig(
            position_tolerance_shares=0.5,
            cash_tolerance_dollars=1.00,  # Allow $1 fee variance
            value_tolerance_pct=0.2,  # Allow 0.2% drift
        )
        reconciler = BrokerReconciler(PaperBroker(), config)

        # Broker slightly different due to fees/slippage
        broker_pos = {"AAPL": Position("AAPL", 100.3, 150.0, 151.0)}
        internal_pos = {"AAPL": Position("AAPL", 100.0, 150.0, 151.0)}

        # Small cash variance from fees (0.50 cents difference)
        result = reconciler.reconcile(
            broker_pos,
            internal_pos,
            9999.50,  # Broker cash after small fee
            9999.00,  # Internal cash before fee processing
            101_043.5,  # Broker value
            101_000.0,  # Internal value estimate (0.043% diff)
        )
        assert result.passed is True

    def test_tolerance_catches_actual_drift(self):
        """When drift exceeds tolerance, should fail."""
        config = ReconciliationConfig(
            position_tolerance_shares=0.5,
            cash_tolerance_dollars=1.00,
            value_tolerance_pct=0.2,
        )
        reconciler = BrokerReconciler(PaperBroker(), config)

        # Broker significantly different
        broker_pos = {"AAPL": Position("AAPL", 105.0, 150.0, 151.0)}  # 5 shares off
        internal_pos = {"AAPL": Position("AAPL", 100.0, 150.0, 151.0)}

        # Large cash variance
        result = reconciler.reconcile(
            broker_pos,
            internal_pos,
            9500.0,  # Broker cash
            10000.0,  # Internal cash (500 diff)
            101_500.0,  # Broker value
            101_000.0,  # Internal value (0.5% diff)
        )
        assert result.passed is False

    def test_reconciliation_logs_detailed_reasons(self):
        """Reconciliation failures should include detailed reason strings."""
        config = ReconciliationConfig()
        reconciler = BrokerReconciler(PaperBroker(), config)

        broker_pos = {"AAPL": Position("AAPL", 115, 150.0, 151.0)}
        internal_pos = {"AAPL": Position("AAPL", 100, 150.0, 151.0)}

        result = reconciler.reconcile(
            broker_pos,
            internal_pos,
            9000.0,
            10000.0,
            103_000.0,
            100_000.0,
        )
        assert result.passed is False
        assert len(result.reasons) >= 3  # Position, cash, value
        assert any("Position mismatch" in r for r in result.reasons)
        assert any("Cash mismatch" in r for r in result.reasons)
        assert any("Portfolio value mismatch" in r for r in result.reasons)

    def test_reconcile_with_no_positions_only_cash_diff(self):
        """Reconciliation should work when only cash differs."""
        config = ReconciliationConfig(cash_tolerance_dollars=0.01)
        reconciler = BrokerReconciler(PaperBroker(), config)

        result = reconciler.reconcile(
            {},  # No positions
            {},  # No positions
            9999.5,  # Broker cash
            10000.0,  # Internal cash (mismatch)
            9999.5,  # Broker value
            10000.0,  # Internal value
        )
        assert result.passed is False
        assert result.cash_diff is not None
        assert len(result.position_diffs) == 0


class MockAlpacaBrokerForTesting:
    """Mock Alpaca broker for testing reconciliation integration."""

    def __init__(self, positions=None, cash=None, portfolio_value=None):
        self._positions = positions or {}
        self._cash = cash or 100_000.0
        self._portfolio_value = portfolio_value or 100_000.0

    def get_positions(self):
        return self._positions

    def get_cash(self):
        return self._cash

    def get_portfolio_value(self):
        return self._portfolio_value


class TestReconciliationWithAlpacaMock:
    """Test reconciliation with a mocked Alpaca-like broker."""

    def test_reconcile_with_alpaca_mock(self):
        """Should work with any broker implementing BrokerBase interface."""
        config = ReconciliationConfig()
        mock_broker = MockAlpacaBrokerForTesting(
            positions={"AAPL": Position("AAPL", 100, 150.0, 151.0)},
            cash=84_900.0,
            portfolio_value=100_000.0,
        )

        reconciler = BrokerReconciler(mock_broker, config)

        result = reconciler.reconcile(
            mock_broker.get_positions(),
            {"AAPL": Position("AAPL", 100, 150.0, 151.0)},  # Internal match
            mock_broker.get_cash(),
            84_900.0,
            mock_broker.get_portfolio_value(),
            100_000.0,
        )
        assert result.passed is True

    def test_reconcile_detects_alpaca_mock_drift(self):
        """Drift detected with Alpaca mock."""
        config = ReconciliationConfig(position_tolerance_shares=5.0)
        mock_broker = MockAlpacaBrokerForTesting(
            positions={"AAPL": Position("AAPL", 110, 150.0, 151.0)},  # More shares
            cash=82_500.0,  # Less cash
            portfolio_value=98_000.0,  # Lower value
        )

        reconciler = BrokerReconciler(mock_broker, config)

        result = reconciler.reconcile(
            mock_broker.get_positions(),
            {"AAPL": Position("AAPL", 100, 150.0, 151.0)},  # Internal
            mock_broker.get_cash(),
            84_900.0,
            mock_broker.get_portfolio_value(),
            100_000.0,
        )
        assert result.passed is False
        assert result.cash_diff is not None
        assert result.value_diff_pct is not None
