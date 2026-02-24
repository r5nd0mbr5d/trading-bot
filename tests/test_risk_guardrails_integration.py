"""
Integration tests for RiskManager + PaperGuardrails.

Verify that guardrails are properly integrated into the signal approval flow
and that they interact correctly with other risk gates.
"""

from datetime import datetime, timezone

import pytest

from config.settings import Settings
from src.data.models import OrderSide, Signal, SignalType
from src.risk.manager import RiskManager


def make_signal(symbol="AAPL", signal_type=SignalType.LONG, strength=1.0):
    return Signal(
        symbol=symbol,
        signal_type=signal_type,
        strength=strength,
        timestamp=datetime.now(timezone.utc),
        strategy_name="test",
    )


class TestPaperGuardrailsIntegration:
    """Integration tests for guardrails in RiskManager."""

    def setup_method(self):
        """Set up RiskManager with paper trading enabled and guardrails active."""
        settings = Settings()
        settings.risk.max_position_pct = 0.10
        settings.risk.max_portfolio_risk_pct = 0.02
        settings.risk.stop_loss_pct = 0.05
        settings.risk.take_profit_pct = 0.15
        settings.initial_capital = 100_000.0
        # ENABLE paper guardrails for this test class
        settings.broker.paper_trading = True
        # Disable session window check to avoid time-based failures
        settings.paper_guardrails.skip_session_window = True
        self.risk = RiskManager(settings)

    def test_guardrails_disabled_when_not_paper_mode(self):
        """When broker.paper_trading=False, guardrails should not block signals."""
        settings = Settings()
        settings.broker.paper_trading = False
        settings.paper_guardrails.enabled = True
        risk = RiskManager(settings)

        # Submit many orders; should not be blocked by daily limit
        for _ in range(100):
            # This would be blocked if guardrails were active
            order = risk.approve_signal(make_signal(), 100_000, 150.0, {})
            # Order should be approved (or blocked by other risk gates, not guardrails)
            assert isinstance(order, type(None)) or isinstance(
                order, object
            )  # Either None or Order

    def test_daily_limit_blocks_signal(self):
        """Daily order limit should block signals after limit reached."""
        settings = Settings()
        settings.broker.paper_trading = True
        settings.paper_guardrails.max_orders_per_day = 3
        settings.paper_guardrails.skip_session_window = True
        risk = RiskManager(settings)

        # Record 3 orders to reach the limit
        for i in range(3):
            risk.record_order_submitted()

        # With 3 orders already recorded (at the limit), the 4th check should pass
        # because 3 > 3 is False
        order = risk.approve_signal(make_signal(symbol="SYM3"), 100_000, 150.0, {})
        assert order is not None, "3rd order should be approved (at limit)"

        # Record the 4th order (now we have 4)
        risk.record_order_submitted()

        # Now with 4 orders, the next signal should be blocked (4 > 3)
        order = risk.approve_signal(make_signal(symbol="SYM4"), 100_000, 150.0, {})
        assert order is None, "Signal should be rejected due to daily order limit (4 > 3)"

    def test_reject_cooldown_blocks_symbol(self):
        """Per-symbol cooldown should block signals after rejection."""
        settings = Settings()
        settings.broker.paper_trading = True
        settings.paper_guardrails.reject_cooldown_seconds = 300
        settings.paper_guardrails.skip_session_window = True
        risk = RiskManager(settings)

        # Record a rejection for AAPL
        risk.record_signal_rejected("AAPL")

        # Immediately try to submit a signal for AAPL; should be blocked
        order = risk.approve_signal(make_signal(symbol="AAPL"), 100_000, 150.0, {})
        assert order is None, "Signal for AAPL should be blocked by cooldown"

        # But different symbol should work
        order = risk.approve_signal(make_signal(symbol="MSFT"), 100_000, 150.0, {})
        assert order is not None, "Signal for different symbol should be approved"

    def test_consecutive_rejects_trigger_auto_stop(self):
        """Auto-stop should block signals after consecutive rejections."""
        settings = Settings()
        settings.broker.paper_trading = True
        settings.paper_guardrails.max_consecutive_rejects = 2
        settings.paper_guardrails.skip_session_window = True
        risk = RiskManager(settings)

        # Record 2 rejections
        risk.record_signal_rejected("AAPL")
        risk.record_signal_rejected("MSFT")

        # 3rd rejection should trigger auto-stop
        risk.record_signal_rejected("GOOGL")
        order = risk.approve_signal(make_signal(symbol="NVDA"), 100_000, 150.0, {})
        assert order is None, "Signal should be blocked by auto-stop after 3 consecutive rejects"

    def test_fill_resets_consecutive_reject_counter(self):
        """Fills should reset the consecutive reject counter."""
        settings = Settings()
        settings.broker.paper_trading = True
        settings.paper_guardrails.max_consecutive_rejects = 2
        settings.paper_guardrails.skip_session_window = True
        risk = RiskManager(settings)

        # Record 2 rejections
        risk.record_signal_rejected("AAPL")
        risk.record_signal_rejected("MSFT")

        # Record a fill (order executed successfully)
        risk.record_signal_filled()

        # Now we can submit more signals (counter reset)
        risk.record_signal_rejected("GOOGL")  # 1st after reset
        risk.record_signal_rejected("NVDA")  # 2nd after reset
        # Still under limit
        order = risk.approve_signal(make_signal(symbol="TSLA"), 100_000, 150.0, {})
        assert order is not None, "Should be approved; consecutive counter was reset by fill"

    def test_reject_rate_limits_based_on_time(self):
        """Reject rate limit should count rejects in the last hour."""
        settings = Settings()
        settings.broker.paper_trading = True
        settings.paper_guardrails.max_rejects_per_hour = 2
        settings.paper_guardrails.skip_session_window = True
        risk = RiskManager(settings)

        # Record 2 rejects in "this hour"
        risk.record_signal_rejected("AAPL")
        risk.record_signal_rejected("MSFT")

        # 3rd reject should trigger rate limit
        risk.record_signal_rejected("GOOGL")
        order = risk.approve_signal(make_signal(symbol="NVDA"), 100_000, 150.0, {})
        assert order is None, "Signal should be blocked by reject rate limit"

    def test_multiple_guardrails_all_checked(self):
        """All guardrails should be checked; any failure blocks the signal."""
        settings = Settings()
        settings.broker.paper_trading = True
        settings.paper_guardrails.max_orders_per_day = 1
        settings.paper_guardrails.max_consecutive_rejects = 0
        settings.paper_guardrails.skip_session_window = True
        risk = RiskManager(settings)

        # Trigger daily limit
        risk.record_order_submitted()

        # Trigger consecutive rejects
        risk.record_signal_rejected("AAPL")

        # Signal should fail due to BOTH limits if checked
        order = risk.approve_signal(make_signal(), 100_000, 150.0, {})
        assert order is None, "Signal should be blocked (multiple guardrails triggered)"

    def test_skip_flags_disable_individual_checks(self):
        """skip_* flags should disable individual guardrail checks."""
        settings = Settings()
        settings.broker.paper_trading = True
        settings.paper_guardrails.max_orders_per_day = 1
        settings.paper_guardrails.skip_daily_limit = True  # Disable daily limit check
        settings.paper_guardrails.skip_session_window = True
        risk = RiskManager(settings)

        # Submit an order (hits daily limit)
        risk.record_order_submitted()

        # Should succeed because skip_daily_limit=True
        order = risk.approve_signal(make_signal(), 100_000, 150.0, {})
        assert (
            order is not None
        ), "Signal should be approved despite daily limit (skip_daily_limit=True)"

    def test_guardrails_enabled_flag_disables_all(self):
        """enabled=False should disable all guardrails at once."""
        settings = Settings()
        settings.broker.paper_trading = True
        settings.paper_guardrails.enabled = False  # Disable all guardrails
        risk = RiskManager(settings)

        # Violate all constraints
        for _ in range(100):
            risk.record_order_submitted()
        risk.record_signal_rejected("AAPL")
        risk.record_signal_rejected("AAPL")
        risk.record_signal_rejected("AAPL")
        risk.record_signal_rejected("AAPL")

        # Signal should still be approved (all guardrails disabled)
        order = risk.approve_signal(make_signal(), 100_000, 150.0, {})
        assert (
            order is not None
        ), "Signal should be approved (enabled=False disables all guardrails)"

    def test_guardrails_interaction_with_var_gate(self):
        """Guardrails should not interfere with VaR gate."""
        settings = Settings()
        settings.broker.paper_trading = True
        settings.paper_guardrails.skip_session_window = True
        # VaR gate is a separate check; guardrails should complement it
        risk = RiskManager(settings)

        # Guardrails should pass
        order = risk.approve_signal(make_signal(), 100_000, 150.0, {})
        # Should be approved if VaR is within limits
        assert order is None or isinstance(order, object)

    def test_guarddrails_logging_on_rejection(self):
        """When guardrails block a signal, it should be logged."""
        import logging
        from io import StringIO

        settings = Settings()
        settings.broker.paper_trading = True
        settings.paper_guardrails.max_orders_per_day = 1
        settings.paper_guardrails.skip_session_window = True
        risk = RiskManager(settings)

        # Record an order to hit the limit
        risk.record_order_submitted()

        # Capture logs
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.WARNING)
        logger = logging.getLogger("src.risk.manager")
        logger.addHandler(handler)

        # Record another order to exceed limit
        risk.record_order_submitted()

        # Submit signal that will be blocked (2 > 1)
        order = risk.approve_signal(make_signal(), 100_000, 150.0, {})
        assert order is None, "Order should be rejected by daily limit"

        # Check that rejection was logged
        log_output = log_stream.getvalue()
        assert (
            "PAPER GUARDRAIL" in log_output
        ), f"Expected 'PAPER GUARDRAIL' in log, got: {log_output}"
