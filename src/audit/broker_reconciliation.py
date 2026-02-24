"""Broker-vs-internal reconciliation checks.

Periodic reconciliation to detect drift between broker account state
and internal portfolio tracking (e.g., due to fees, FX adjustments, data lag).
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from config.settings import ReconciliationConfig
from src.data.models import OrderStatus, Position
from src.execution.broker import BrokerBase

logger = logging.getLogger(__name__)


@dataclass
class PositionDiff:
    """Difference for one symbol between broker and internal state."""

    symbol: str
    broker_qty: float
    internal_qty: float
    qty_diff: float


@dataclass
class OrderLifecycleDiff:
    """Difference in lifecycle state for one order between broker/internal."""

    order_id: str
    broker_status: str
    internal_status: str


@dataclass
class ReconciliationResult:
    """Result of a full reconciliation check."""

    passed: bool
    timestamp: str
    position_diffs: List[PositionDiff] = field(default_factory=list)
    order_diffs: List[OrderLifecycleDiff] = field(default_factory=list)
    cash_diff: Optional[float] = None
    value_diff: Optional[float] = None
    value_diff_pct: Optional[float] = None
    reasons: List[str] = field(default_factory=list)  # Why checks failed


class BrokerReconciler:
    """Periodic reconciliation between broker and internal portfolio state."""

    def __init__(
        self,
        broker: BrokerBase,
        config: ReconciliationConfig,
    ):
        """Initialize reconciler.

        Args:
            broker: BrokerBase instance (AlpacaBroker, PaperBroker, etc.)
            config: ReconciliationConfig with tolerance thresholds
        """
        self.broker = broker
        self.config = config
        self.fill_count = 0  # Track fills for interval-based reconciliation

    def record_fill(self) -> None:
        """Increment fill counter. Call this after each fill event."""
        self.fill_count += 1

    def should_reconcile_now(self) -> bool:
        """Return True if reconciliation interval has elapsed."""
        if not self.config.enabled:
            return False
        if self.fill_count >= self.config.reconcile_every_n_fills:
            return True
        return False

    def reset_counter(self) -> None:
        """Reset fill counter after reconciliation."""
        self.fill_count = 0

    def compare_positions(
        self,
        broker_positions: Dict[str, Position],
        internal_positions: Dict[str, Position],
    ) -> List[PositionDiff]:
        """Compare broker positions vs internal positions.

        Returns:
            List of PositionDiff objects for symbols with mismatches.
            Empty list if all positions match within tolerance.
        """
        if self.config.skip_position_check:
            return []

        diffs = []

        # Check symbols in broker account
        for symbol, broker_pos in broker_positions.items():
            internal_pos = internal_positions.get(symbol)
            internal_qty = internal_pos.qty if internal_pos else 0.0

            qty_diff = abs(broker_pos.qty - internal_qty)
            if qty_diff > self.config.position_tolerance_shares:
                diffs.append(
                    PositionDiff(
                        symbol=symbol,
                        broker_qty=broker_pos.qty,
                        internal_qty=internal_qty,
                        qty_diff=qty_diff,
                    )
                )

        # Check symbols only in internal positions (might have been sold by broker)
        for symbol, internal_pos in internal_positions.items():
            if symbol not in broker_positions:
                broker_qty = 0.0
                qty_diff = abs(broker_qty - internal_pos.qty)
                if qty_diff > self.config.position_tolerance_shares:
                    diffs.append(
                        PositionDiff(
                            symbol=symbol,
                            broker_qty=broker_qty,
                            internal_qty=internal_pos.qty,
                            qty_diff=qty_diff,
                        )
                    )

        return diffs

    @staticmethod
    def _normalize_order_status(status: str | OrderStatus) -> str:
        if isinstance(status, OrderStatus):
            return status.value
        return str(status or "").strip().lower()

    def compare_order_lifecycle(
        self,
        broker_orders: Dict[str, str | OrderStatus],
        internal_orders: Dict[str, str | OrderStatus],
    ) -> List[OrderLifecycleDiff]:
        """Compare broker/internal order lifecycle states by order id.

        Tracks pending/partial/cancel/filled/rejected drift and missing order IDs.
        """
        diffs: List[OrderLifecycleDiff] = []
        all_ids = set(broker_orders.keys()) | set(internal_orders.keys())

        for order_id in all_ids:
            broker_state = self._normalize_order_status(broker_orders.get(order_id, "missing"))
            internal_state = self._normalize_order_status(internal_orders.get(order_id, "missing"))

            if broker_state != internal_state:
                diffs.append(
                    OrderLifecycleDiff(
                        order_id=str(order_id),
                        broker_status=broker_state,
                        internal_status=internal_state,
                    )
                )

        return diffs

    def compare_cash(
        self,
        broker_cash: float,
        internal_cash: float,
    ) -> Optional[float]:
        """Compare broker cash vs internal cash.

        Returns:
            Cash difference (broker - internal) if mismatch exceeds tolerance.
            None if cash matches within tolerance or check is skipped.
        """
        if self.config.skip_cash_check:
            return None

        diff = abs(broker_cash - internal_cash)
        if diff > self.config.cash_tolerance_dollars:
            return broker_cash - internal_cash

        return None

    def compare_portfolio_value(
        self,
        broker_value: float,
        internal_value: float,
    ) -> Optional[float]:
        """Compare broker portfolio value vs internal calculation.

        Returns:
            Value difference percentage if mismatch exceeds tolerance.
            None if value matches within tolerance or check is skipped.
        """
        if self.config.skip_value_check:
            return None

        if internal_value <= 0:
            # Can't compute percentage diff if internal value is zero/negative
            return None

        diff_pct = abs(broker_value - internal_value) / internal_value * 100
        if diff_pct > self.config.value_tolerance_pct:
            return diff_pct

        return None

    def reconcile(
        self,
        broker_positions: Dict[str, Position],
        internal_positions: Dict[str, Position],
        broker_cash: float,
        internal_cash: float,
        broker_value: float,
        internal_value: float,
    ) -> ReconciliationResult:
        """Run full reconciliation and gather all mismatches.

        Returns:
            ReconciliationResult with details of all mismatches and reasons for failure.
        """
        from datetime import datetime, timezone

        result = ReconciliationResult(
            passed=True,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # Check positions
        position_diffs = self.compare_positions(broker_positions, internal_positions)
        if position_diffs:
            result.passed = False
            result.position_diffs = position_diffs
            for diff in position_diffs:
                reason = (
                    f"Position mismatch [{diff.symbol}]: "
                    f"broker={diff.broker_qty} vs internal={diff.internal_qty} "
                    f"(diff={diff.qty_diff:.2f})"
                )
                result.reasons.append(reason)

        # Check cash
        cash_diff = self.compare_cash(broker_cash, internal_cash)
        if cash_diff is not None:
            result.passed = False
            result.cash_diff = cash_diff
            reason = (
                f"Cash mismatch: broker={broker_cash:.2f} vs internal={internal_cash:.2f} "
                f"(diff={cash_diff:.2f})"
            )
            result.reasons.append(reason)

        # Check portfolio value
        value_diff_pct = self.compare_portfolio_value(broker_value, internal_value)
        if value_diff_pct is not None:
            result.passed = False
            result.value_diff_pct = value_diff_pct
            reason = (
                f"Portfolio value mismatch: broker={broker_value:.2f} vs "
                f"internal={internal_value:.2f} (diff={value_diff_pct:.2f}%)"
            )
            result.reasons.append(reason)

        return result

    def reconcile_with_order_lifecycle(
        self,
        broker_positions: Dict[str, Position],
        internal_positions: Dict[str, Position],
        broker_cash: float,
        internal_cash: float,
        broker_value: float,
        internal_value: float,
        broker_orders: Dict[str, str | OrderStatus],
        internal_orders: Dict[str, str | OrderStatus],
    ) -> ReconciliationResult:
        """Run full reconciliation including order lifecycle status checks."""
        result = self.reconcile(
            broker_positions=broker_positions,
            internal_positions=internal_positions,
            broker_cash=broker_cash,
            internal_cash=internal_cash,
            broker_value=broker_value,
            internal_value=internal_value,
        )

        order_diffs = self.compare_order_lifecycle(
            broker_orders=broker_orders,
            internal_orders=internal_orders,
        )
        if order_diffs:
            result.passed = False
            result.order_diffs = order_diffs
            for diff in order_diffs:
                result.reasons.append(
                    f"Order lifecycle mismatch [{diff.order_id}]: "
                    f"broker={diff.broker_status} vs internal={diff.internal_status}"
                )

        return result
