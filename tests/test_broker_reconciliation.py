"""Unit tests for BrokerReconciler."""

from config.settings import ReconciliationConfig
from src.audit.broker_reconciliation import (
    BrokerReconciler,
    OrderLifecycleDiff,
)
from src.data.models import Position
from src.execution.broker import PaperBroker


class TestPositionComparison:
    """Test position reconciliation logic."""

    def test_no_positions_no_diff(self):
        """Empty positions on both sides should match."""
        config = ReconciliationConfig(position_tolerance_shares=1.0)
        reconciler = BrokerReconciler(PaperBroker(), config)

        diffs = reconciler.compare_positions({}, {})
        assert diffs == []

    def test_matching_positions_within_tolerance(self):
        """Positions within tolerance should not differ."""
        config = ReconciliationConfig(position_tolerance_shares=1.0)
        reconciler = BrokerReconciler(PaperBroker(), config)

        broker_pos = {"AAPL": Position("AAPL", 100, 150.0, 151.0)}
        internal_pos = {"AAPL": Position("AAPL", 100, 150.0, 151.0)}

        diffs = reconciler.compare_positions(broker_pos, internal_pos)
        assert diffs == []

    def test_position_diff_within_tolerance(self):
        """Differences within tolerance should not be flagged."""
        config = ReconciliationConfig(position_tolerance_shares=1.0)
        reconciler = BrokerReconciler(PaperBroker(), config)

        broker_pos = {"AAPL": Position("AAPL", 100.5, 150.0, 151.0)}
        internal_pos = {"AAPL": Position("AAPL", 100.0, 150.0, 151.0)}

        diffs = reconciler.compare_positions(broker_pos, internal_pos)
        assert diffs == []

    def test_position_diff_exceeds_tolerance(self):
        """Differences exceeding tolerance should be flagged."""
        config = ReconciliationConfig(position_tolerance_shares=1.0)
        reconciler = BrokerReconciler(PaperBroker(), config)

        broker_pos = {"AAPL": Position("AAPL", 105.0, 150.0, 151.0)}
        internal_pos = {"AAPL": Position("AAPL", 100.0, 150.0, 151.0)}

        diffs = reconciler.compare_positions(broker_pos, internal_pos)
        assert len(diffs) == 1
        assert diffs[0].symbol == "AAPL"
        assert diffs[0].broker_qty == 105.0
        assert diffs[0].internal_qty == 100.0
        assert diffs[0].qty_diff == 5.0

    def test_broker_has_extra_position(self):
        """Broker with position not in internal should be flagged."""
        config = ReconciliationConfig(position_tolerance_shares=1.0)
        reconciler = BrokerReconciler(PaperBroker(), config)

        broker_pos = {
            "AAPL": Position("AAPL", 100.0, 150.0, 151.0),
            "MSFT": Position("MSFT", 50.0, 300.0, 305.0),
        }
        internal_pos = {"AAPL": Position("AAPL", 100.0, 150.0, 151.0)}

        diffs = reconciler.compare_positions(broker_pos, internal_pos)
        assert len(diffs) == 1
        assert diffs[0].symbol == "MSFT"
        assert diffs[0].broker_qty == 50.0
        assert diffs[0].internal_qty == 0.0

    def test_internal_has_extra_position(self):
        """Internal with position not in broker should be flagged."""
        config = ReconciliationConfig(position_tolerance_shares=1.0)
        reconciler = BrokerReconciler(PaperBroker(), config)

        broker_pos = {"AAPL": Position("AAPL", 100.0, 150.0, 151.0)}
        internal_pos = {
            "AAPL": Position("AAPL", 100.0, 150.0, 151.0),
            "MSFT": Position("MSFT", 50.0, 300.0, 305.0),
        }

        diffs = reconciler.compare_positions(broker_pos, internal_pos)
        assert len(diffs) == 1
        assert diffs[0].symbol == "MSFT"
        assert diffs[0].broker_qty == 0.0
        assert diffs[0].internal_qty == 50.0

    def test_skip_position_check(self):
        """skip_position_check=True should disable all checks."""
        config = ReconciliationConfig(skip_position_check=True)
        reconciler = BrokerReconciler(PaperBroker(), config)

        broker_pos = {"AAPL": Position("AAPL", 1000.0, 150.0, 151.0)}
        internal_pos = {"AAPL": Position("AAPL", 0.0, 150.0, 151.0)}

        diffs = reconciler.compare_positions(broker_pos, internal_pos)
        assert diffs == []


class TestCashComparison:
    """Test cash reconciliation logic."""

    def test_matching_cash_returns_none(self):
        """Matching cash should return None."""
        config = ReconciliationConfig(cash_tolerance_dollars=0.01)
        reconciler = BrokerReconciler(PaperBroker(), config)

        diff = reconciler.compare_cash(10000.0, 10000.0)
        assert diff is None

    def test_cash_diff_within_tolerance_returns_none(self):
        """Cash diff within tolerance should return None."""
        config = ReconciliationConfig(cash_tolerance_dollars=0.01)
        reconciler = BrokerReconciler(PaperBroker(), config)

        diff = reconciler.compare_cash(10000.005, 10000.0)
        assert diff is None

    def test_cash_diff_exceeds_tolerance_returns_diff(self):
        """Cash diff exceeding tolerance should return the difference."""
        config = ReconciliationConfig(cash_tolerance_dollars=0.01)
        reconciler = BrokerReconciler(PaperBroker(), config)

        diff = reconciler.compare_cash(10000.1, 10000.0)
        assert diff is not None
        assert abs(diff - 0.1) < 0.001

    def test_negative_cash_diff(self):
        """Negative cash diff (broker < internal) should be detected."""
        config = ReconciliationConfig(cash_tolerance_dollars=0.01)
        reconciler = BrokerReconciler(PaperBroker(), config)

        diff = reconciler.compare_cash(9999.9, 10000.0)
        assert diff is not None
        assert abs(diff - (-0.1)) < 0.001

    def test_skip_cash_check(self):
        """skip_cash_check=True should disable check."""
        config = ReconciliationConfig(skip_cash_check=True)
        reconciler = BrokerReconciler(PaperBroker(), config)

        diff = reconciler.compare_cash(0.0, 10000.0)
        assert diff is None


class TestValueComparison:
    """Test portfolio value reconciliation logic."""

    def test_matching_value_returns_none(self):
        """Matching values should return None."""
        config = ReconciliationConfig(value_tolerance_pct=0.5)
        reconciler = BrokerReconciler(PaperBroker(), config)

        diff = reconciler.compare_portfolio_value(100_000.0, 100_000.0)
        assert diff is None

    def test_value_diff_within_tolerance_returns_none(self):
        """Value diff within tolerance should return None."""
        config = ReconciliationConfig(value_tolerance_pct=0.5)
        reconciler = BrokerReconciler(PaperBroker(), config)

        # 0.2% diff is within 0.5% tolerance
        diff = reconciler.compare_portfolio_value(100_200.0, 100_000.0)
        assert diff is None

    def test_value_diff_exceeds_tolerance_returns_pct(self):
        """Value diff exceeding tolerance should return percentage."""
        config = ReconciliationConfig(value_tolerance_pct=0.5)
        reconciler = BrokerReconciler(PaperBroker(), config)

        # 1% diff exceeds 0.5% tolerance
        diff = reconciler.compare_portfolio_value(101_000.0, 100_000.0)
        assert diff is not None
        assert abs(diff - 1.0) < 0.01

    def test_zero_internal_value_returns_none(self):
        """Zero internal value should return None (can't compute percentage)."""
        config = ReconciliationConfig(value_tolerance_pct=0.5)
        reconciler = BrokerReconciler(PaperBroker(), config)

        diff = reconciler.compare_portfolio_value(100.0, 0.0)
        assert diff is None

    def test_negative_internal_value_returns_none(self):
        """Negative internal value should return None (can't compute percentage)."""
        config = ReconciliationConfig(value_tolerance_pct=0.5)
        reconciler = BrokerReconciler(PaperBroker(), config)

        diff = reconciler.compare_portfolio_value(100.0, -100.0)
        assert diff is None

    def test_skip_value_check(self):
        """skip_value_check=True should disable check."""
        config = ReconciliationConfig(skip_value_check=True)
        reconciler = BrokerReconciler(PaperBroker(), config)

        diff = reconciler.compare_portfolio_value(0.0, 100_000.0)
        assert diff is None


class TestFullReconciliation:
    """Test full reconcile() method."""

    def test_all_pass_returns_passed_true(self):
        """All checks passing should return passed=True."""
        config = ReconciliationConfig()
        reconciler = BrokerReconciler(PaperBroker(), config)

        broker_pos = {"AAPL": Position("AAPL", 100.0, 150.0, 151.0)}
        internal_pos = {"AAPL": Position("AAPL", 100.0, 150.0, 151.0)}

        result = reconciler.reconcile(
            broker_pos, internal_pos, 10000.0, 10000.0, 100_000.0, 100_000.0
        )
        assert result.passed is True
        assert result.position_diffs == []
        assert result.cash_diff is None
        assert result.value_diff_pct is None
        assert result.reasons == []

    def test_single_check_failure_returns_passed_false(self):
        """Any single check failure should return passed=False."""
        config = ReconciliationConfig(
            position_tolerance_shares=1.0,
            cash_tolerance_dollars=0.01,
            value_tolerance_pct=0.5,
        )
        reconciler = BrokerReconciler(PaperBroker(), config)

        # Position mismatch exceeds tolerance
        broker_pos = {"AAPL": Position("AAPL", 115.0, 150.0, 151.0)}
        internal_pos = {"AAPL": Position("AAPL", 100.0, 150.0, 151.0)}

        result = reconciler.reconcile(
            broker_pos, internal_pos, 10000.0, 10000.0, 100_000.0, 100_000.0
        )
        assert result.passed is False
        assert len(result.position_diffs) == 1
        assert len(result.reasons) == 1

    def test_multiple_check_failures_accumulate(self):
        """Multiple check failures should accumulate."""
        config = ReconciliationConfig(
            position_tolerance_shares=1.0,
            cash_tolerance_dollars=0.01,
            value_tolerance_pct=0.5,
        )
        reconciler = BrokerReconciler(PaperBroker(), config)

        # All three checks fail
        broker_pos = {"AAPL": Position("AAPL", 115.0, 150.0, 151.0)}
        internal_pos = {"AAPL": Position("AAPL", 100.0, 150.0, 151.0)}

        result = reconciler.reconcile(
            broker_pos,
            internal_pos,
            9999.0,  # Cash mismatch
            10000.0,
            101_000.0,  # Value mismatch
            100_000.0,
        )
        assert result.passed is False
        assert len(result.position_diffs) == 1
        assert result.cash_diff is not None
        assert result.value_diff_pct is not None
        assert len(result.reasons) == 3

    def test_timestamp_included_in_result(self):
        """Result should include ISO timestamp."""
        config = ReconciliationConfig()
        reconciler = BrokerReconciler(PaperBroker(), config)

        result = reconciler.reconcile({}, {}, 10000.0, 10000.0, 100_000.0, 100_000.0)
        assert result.timestamp is not None
        assert "T" in result.timestamp  # ISO format includes 'T'


class TestFillCounterLogic:
    """Test fill counter and reconciliation interval."""

    def test_should_reconcile_when_disabled(self):
        """should_reconcile_now should return False if disabled."""
        config = ReconciliationConfig(enabled=False)
        reconciler = BrokerReconciler(PaperBroker(), config)

        reconciler.fill_count = 100
        assert reconciler.should_reconcile_now() is False

    def test_should_reconcile_returns_false_before_interval(self):
        """should_reconcile_now should return False before interval."""
        config = ReconciliationConfig(enabled=True, reconcile_every_n_fills=10)
        reconciler = BrokerReconciler(PaperBroker(), config)

        reconciler.fill_count = 5
        assert reconciler.should_reconcile_now() is False

    def test_should_reconcile_returns_true_at_interval(self):
        """should_reconcile_now should return True at interval."""
        config = ReconciliationConfig(enabled=True, reconcile_every_n_fills=10)
        reconciler = BrokerReconciler(PaperBroker(), config)

        reconciler.fill_count = 10
        assert reconciler.should_reconcile_now() is True

    def test_record_fill_increments_counter(self):
        """record_fill should increment counter."""
        config = ReconciliationConfig()
        reconciler = BrokerReconciler(PaperBroker(), config)

        assert reconciler.fill_count == 0
        reconciler.record_fill()
        assert reconciler.fill_count == 1
        reconciler.record_fill()
        assert reconciler.fill_count == 2


class TestOrderLifecycleComparison:
    """Test order lifecycle reconciliation logic."""

    def test_matching_order_states_no_diff(self):
        config = ReconciliationConfig()
        reconciler = BrokerReconciler(PaperBroker(), config)

        diffs = reconciler.compare_order_lifecycle(
            broker_orders={"o1": "filled", "o2": "pending"},
            internal_orders={"o1": "filled", "o2": "pending"},
        )
        assert diffs == []

    def test_mismatched_order_states_flagged(self):
        config = ReconciliationConfig()
        reconciler = BrokerReconciler(PaperBroker(), config)

        diffs = reconciler.compare_order_lifecycle(
            broker_orders={"o1": "filled"},
            internal_orders={"o1": "pending"},
        )
        assert len(diffs) == 1
        assert isinstance(diffs[0], OrderLifecycleDiff)
        assert diffs[0].order_id == "o1"

    def test_missing_order_id_flagged(self):
        config = ReconciliationConfig()
        reconciler = BrokerReconciler(PaperBroker(), config)

        diffs = reconciler.compare_order_lifecycle(
            broker_orders={"o1": "cancelled"},
            internal_orders={},
        )
        assert len(diffs) == 1
        assert diffs[0].broker_status == "cancelled"
        assert diffs[0].internal_status == "missing"

    def test_reconcile_with_order_lifecycle_appends_reasons(self):
        config = ReconciliationConfig()
        reconciler = BrokerReconciler(PaperBroker(), config)

        result = reconciler.reconcile_with_order_lifecycle(
            broker_positions={},
            internal_positions={},
            broker_cash=10000.0,
            internal_cash=10000.0,
            broker_value=100000.0,
            internal_value=100000.0,
            broker_orders={"o1": "filled"},
            internal_orders={"o1": "pending"},
        )

        assert result.passed is False
        assert len(result.order_diffs) == 1
        assert any("Order lifecycle mismatch" in reason for reason in result.reasons)

    def test_reset_counter_clears_fill_count(self):
        """reset_counter should zero out fill_count."""
        config = ReconciliationConfig()
        reconciler = BrokerReconciler(PaperBroker(), config)

        reconciler.fill_count = 15
        reconciler.reset_counter()
        assert reconciler.fill_count == 0


class TestConfigurationFlags:
    """Test individual skip flags."""

    def test_all_skip_flags_disable_all_checks(self):
        """All skip flags set should disable all checks."""
        config = ReconciliationConfig(
            skip_position_check=True,
            skip_cash_check=True,
            skip_value_check=True,
        )
        reconciler = BrokerReconciler(PaperBroker(), config)

        # All checks fail
        broker_pos = {"AAPL": Position("AAPL", 0.0, 150.0, 151.0)}
        internal_pos = {"AAPL": Position("AAPL", 100.0, 150.0, 151.0)}

        result = reconciler.reconcile(broker_pos, internal_pos, 0.0, 10000.0, 0.0, 100_000.0)
        assert result.passed is True
        assert result.reasons == []

    def test_enabled_false_disables_all_checks_on_reconcile(self):
        """enabled=False should not affect individual compare methods (skip flags used for that).

        Note: enabled flag is checked by should_reconcile_now(), not by reconcile() itself.
        The skip_* flags are the proper way to disable individual checks.
        """
        config = ReconciliationConfig(
            enabled=False,
            skip_position_check=True,
            skip_cash_check=True,
            skip_value_check=True,
        )
        reconciler = BrokerReconciler(PaperBroker(), config)

        # reconcile() will pass due to skip flags
        result = reconciler.reconcile({}, {}, 0.0, 10000.0, 0.0, 100_000.0)
        assert result.passed is True


class TestEdgeCases:
    """Test edge case scenarios."""

    def test_empty_positions_no_cash_no_value(self):
        """Zero positions, cash, and value should pass."""
        config = ReconciliationConfig()
        reconciler = BrokerReconciler(PaperBroker(), config)

        result = reconciler.reconcile({}, {}, 0.0, 0.0, 0.0, 0.0)
        assert result.passed is True

    def test_large_position_count(self):
        """Reconciliation should handle many positions."""
        config = ReconciliationConfig(position_tolerance_shares=1.0)
        reconciler = BrokerReconciler(PaperBroker(), config)

        # 100 matching positions
        broker_pos = {f"SYM{i}": Position(f"SYM{i}", 100.0 + i, 100.0, 101.0) for i in range(100)}
        internal_pos = {f"SYM{i}": Position(f"SYM{i}", 100.0 + i, 100.0, 101.0) for i in range(100)}

        result = reconciler.reconcile(
            broker_pos, internal_pos, 50000.0, 50000.0, 1_000_000.0, 1_000_000.0
        )
        assert result.passed is True
        assert len(result.position_diffs) == 0

    def test_fractional_shares(self):
        """Fractional shares should be supported (Alpaca allows them)."""
        config = ReconciliationConfig(position_tolerance_shares=0.01)
        reconciler = BrokerReconciler(PaperBroker(), config)

        broker_pos = {"AAPL": Position("AAPL", 100.123, 150.0, 151.0)}
        internal_pos = {"AAPL": Position("AAPL", 100.115, 150.0, 151.0)}

        # Diff is 0.008 shares, within 0.01 tolerance
        diffs = reconciler.compare_positions(broker_pos, internal_pos)
        assert diffs == []

    def test_very_small_cash_tolerance(self):
        """Should support tight cash tolerance (e.g., penny rounding)."""
        config = ReconciliationConfig(cash_tolerance_dollars=0.001)  # 0.1 cent
        reconciler = BrokerReconciler(PaperBroker(), config)

        diff = reconciler.compare_cash(10000.0005, 10000.0)
        assert diff is None

        diff = reconciler.compare_cash(10000.002, 10000.0)
        assert diff is not None
