"""Trading loop handler — encapsulates bar processing and event callbacks.

Responsible for:
- Processing each bar (quality checks, strategy signals, risk approval, order submission)
- Managing stream lifecycle events (heartbeat, errors)
- Coordinating portfolio snapshots and P&L tracking
"""

import logging
from datetime import datetime, timezone
from typing import Callable, Optional

from config.settings import Settings
from src.audit.logger import AuditLogger
from src.data.models import Bar, Order, Signal
from src.execution.broker import BrokerBase
from src.execution.market_hours import is_market_open
from src.execution.resilience import run_broker_operation
from src.portfolio.tracker import PortfolioTracker
from src.risk.data_quality import DataQualityGuard
from src.risk.kill_switch import KillSwitch
from src.risk.manager import RiskManager
from src.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


def build_runtime_broker(settings: Settings) -> BrokerBase:
    """Build runtime broker with crypto primary/fallback routing."""
    from src.execution.broker import (
        AlpacaBroker,
        BinanceBroker,
        BrokerConnectionError,
        CoinbaseBroker,
    )
    from src.execution.ibkr_broker import IBKRBroker

    has_crypto_symbol = any(settings.is_crypto(symbol) for symbol in settings.data.symbols)
    if has_crypto_symbol:
        primary = str(settings.broker.crypto_primary_provider or "coinbase").strip().lower()
        fallback = str(settings.broker.crypto_fallback_provider or "binance").strip().lower()
        provider_map = {
            "coinbase": CoinbaseBroker,
            "binance": BinanceBroker,
        }

        primary_cls = provider_map.get(primary, CoinbaseBroker)
        fallback_cls = provider_map.get(fallback, BinanceBroker)

        try:
            return primary_cls(settings)
        except BrokerConnectionError as exc:
            logger.warning(
                "Coinbase unavailable, routing to Binance fallback: %s",
                exc,
            )
            return fallback_cls(settings)

    if settings.broker.provider.lower() == "ibkr":
        return IBKRBroker(settings)
    return AlpacaBroker(settings)


class TradingLoopHandler:
    """Encapsulates the main bar-processing logic for paper/live trading.

    Responsibilities:
    - Data quality validation for each bar
    - Strategy signal generation
    - Risk-approved order submission
    - Portfolio and P&L tracking
    - Audit event logging

    Designed to be called from async streaming context (feed.stream).
    """

    def __init__(
        self,
        settings: Settings,
        strategy: BaseStrategy,
        risk: RiskManager,
        broker: BrokerBase,
        tracker: PortfolioTracker,
        data_quality: DataQualityGuard,
        kill_switch: KillSwitch,
        audit: AuditLogger,
        enqueue_audit,
        broker_retry_state: dict,
    ):
        """Initialize trading loop handler.

        Args:
            settings: Configuration
            strategy: Strategy instance
            risk: Risk manager
            broker: Broker instance
            tracker: Portfolio tracker
            data_quality: Data quality guard
            kill_switch: Kill switch instance
            audit: Audit logger
            enqueue_audit: Async audit callback
            broker_retry_state: Shared retry state dict
        """
        self.settings = settings
        self.strategy = strategy
        self.risk = risk
        self.broker = broker
        self.tracker = tracker
        self.data_quality = data_quality
        self.kill_switch = kill_switch
        self.audit = audit
        self.enqueue_audit = enqueue_audit
        self.broker_retry_state = broker_retry_state
        self.prev_portfolio_value = 0.0
        # Optional event hooks — set by BarPipeline; None means no-op
        self._on_signal_generated: Optional[Callable[[Signal], None]] = None
        self._on_order_submitted: Optional[Callable[[Order], None]] = None
        self._on_fill_received: Optional[Callable[[Order], None]] = None

    def _prewarm_strategy(self, feed) -> None:
        """Pre-warm strategy with recent 5-day history."""
        logger.info("Pre-warming strategy with recent 5-day history…")
        for symbol in self.settings.data.symbols:
            try:
                df = feed.fetch_historical(symbol, period="5d", interval="1m")
                bars = feed.to_bars(symbol, df)
                for bar in bars:
                    self.strategy.on_bar(bar)
                logger.info(
                    f"  {symbol}: {len(bars)} bars loaded "
                    f"(strategy ready: {len(bars)} >= {self.strategy.min_bars_required()})"
                )
            except Exception as exc:
                logger.warning(f"  {symbol}: pre-warm failed — {exc}")
                self.enqueue_audit(
                    "PREWARM_ERROR",
                    {"error": str(exc)},
                    symbol=symbol,
                    strategy=self.settings.strategy.name,
                    severity="warning",
                )

    def initialize_portfolio_value(self) -> None:
        """Fetch and store initial portfolio value."""
        try:
            self.prev_portfolio_value = run_broker_operation(
                self.settings,
                "get_portfolio_value",
                self.broker.get_portfolio_value,
                retry_state=self.broker_retry_state,
                kill_switch=self.kill_switch,
                enqueue_audit=self.enqueue_audit,
                strategy=self.settings.strategy.name,
            )
            logger.info(f"Initial portfolio value: ${self.prev_portfolio_value:,.2f}")
        except RuntimeError as exc:
            logger.error("Failed to fetch initial portfolio value: %s", exc)
            self.prev_portfolio_value = 0.0

    def on_bar(self, bar: Bar) -> None:
        """Process a single bar (main per-bar logic).

        Executes:
        1. Data quality checks (stale data, gaps)
        2. Kill-switch validation
        3. Strategy signal generation
        4. Risk-approved order submission
        5. VaR tracking
        6. Portfolio snapshot and P&L calculation

        Args:
            bar: OHLCV bar with timestamp
        """
        if not self._check_data_quality(bar):
            return

        if (
            self.settings.enforce_market_hours
            and not self.settings.is_crypto(bar.symbol)
            and not is_market_open(
            bar.symbol, bar.timestamp
            )
        ):
            logger.debug(
                "Skipping %s bar at %s: market closed",
                bar.symbol,
                bar.timestamp.isoformat(),
            )
            return

        if not self._check_kill_switch(bar):
            return

        signal = self._generate_signal(bar)
        if signal:
            price = bar.close
            order = self._gate_risk(signal, price)
            if order:
                self._submit_order(order, signal, price)

        self._update_var(bar)
        self._snapshot_portfolio(bar)

    def _check_data_quality(self, bar: Bar) -> bool:
        dq_reasons = self.data_quality.check_bar(
            bar.symbol, bar.timestamp, datetime.now(timezone.utc)
        )
        if dq_reasons and self.settings.data_quality.enable_stale_check:
            self.enqueue_audit(
                "DATA_QUALITY_BLOCK",
                {"reasons": dq_reasons, "bar_ts": bar.timestamp.isoformat()},
                symbol=bar.symbol,
                strategy=self.settings.strategy.name,
                severity="warning",
            )
            if "stale_data_max_consecutive" in dq_reasons:
                self.kill_switch.trigger("stale_data_max_consecutive")
                self.enqueue_audit(
                    "KILL_SWITCH_TRIGGERED",
                    {"reason": "stale_data_max_consecutive"},
                    symbol=bar.symbol,
                    strategy=self.settings.strategy.name,
                    severity="critical",
                )
            return False
        return True

    def _check_kill_switch(self, bar: Bar) -> bool:
        try:
            self.kill_switch.check_and_raise()
            return True
        except RuntimeError as exc:
            logger.critical(str(exc))
            self.enqueue_audit(
                "KILL_SWITCH_ACTIVE",
                {"error": str(exc)},
                symbol=bar.symbol,
                strategy=self.settings.strategy.name,
                severity="critical",
            )
            return False

    def _generate_signal(self, bar: Bar) -> Optional[Signal]:
        signal = self.strategy.on_bar(bar)
        if not signal:
            return None
        self.enqueue_audit(
            "SIGNAL",
            {
                "type": signal.signal_type.value,
                "strength": signal.strength,
                "metadata": signal.metadata,
                "timestamp": signal.timestamp.isoformat(),
            },
            symbol=signal.symbol,
            strategy=signal.strategy_name,
        )
        if self._on_signal_generated:
            self._on_signal_generated(signal)
        return signal

    def _gate_risk(self, signal: Signal, price: float) -> Optional[Order]:
        try:
            positions = run_broker_operation(
                self.settings,
                "get_positions",
                self.broker.get_positions,
                retry_state=self.broker_retry_state,
                kill_switch=self.kill_switch,
                enqueue_audit=self.enqueue_audit,
                symbol=signal.symbol,
                strategy=signal.strategy_name,
            )
            portfolio_value = run_broker_operation(
                self.settings,
                "get_portfolio_value",
                self.broker.get_portfolio_value,
                retry_state=self.broker_retry_state,
                kill_switch=self.kill_switch,
                enqueue_audit=self.enqueue_audit,
                symbol=signal.symbol,
                strategy=signal.strategy_name,
            )
        except RuntimeError as exc:
            logger.error("Broker unavailable during risk checks: %s", exc)
            return None

        order = self.risk.approve_signal(signal, portfolio_value, price, positions)
        if not order:
            rejection = self.risk.get_last_rejection()
            if rejection.get("code") == "SECTOR_CONCENTRATION_REJECTED":
                self.enqueue_audit(
                    "SECTOR_CONCENTRATION_REJECTED",
                    {"reason": rejection.get("reason", "")},
                    symbol=signal.symbol,
                    strategy=signal.strategy_name,
                    severity="warning",
                )
            if rejection.get("code") == "CORRELATION_LIMIT":
                self.enqueue_audit(
                    "CORRELATION_LIMIT",
                    {"reason": rejection.get("reason", "")},
                    symbol=signal.symbol,
                    strategy=signal.strategy_name,
                    severity="warning",
                )
        return order

    def _submit_order(self, order: Order, signal: Signal, price: float) -> None:
        self.enqueue_audit(
            "ORDER_SUBMITTED",
            {
                "side": order.side.value,
                "qty": order.qty,
                "stop_loss": order.stop_loss,
                "take_profit": order.take_profit,
                "price_reference": price,
            },
            symbol=order.symbol,
            strategy=signal.strategy_name,
        )
        if self._on_order_submitted:
            self._on_order_submitted(order)
        try:
            filled = run_broker_operation(
                self.settings,
                "submit_order",
                lambda: self.broker.submit_order(order),
                retry_state=self.broker_retry_state,
                kill_switch=self.kill_switch,
                enqueue_audit=self.enqueue_audit,
                symbol=order.symbol,
                strategy=signal.strategy_name,
            )
            if filled.status.value == "filled":
                logger.info(
                    f"ORDER FILLED: {filled.side.value.upper()} "
                    f"{filled.qty} {filled.symbol} @ ~${price:.2f}"
                )
                fill_price = filled.filled_price or price
                commission_per_share = float(
                    getattr(self.settings.broker, "commission_per_share", 0.0) or 0.0
                )
                estimated_fee = round(max(filled.qty, 0.0) * commission_per_share, 6)
                slippage_pct_vs_signal = 0.0
                if price > 0:
                    slippage_pct_vs_signal = round((fill_price - price) / price, 8)
                currency = "USD"
                if self.settings.broker.provider.lower() == "ibkr":
                    currency = self.broker.get_symbol_currency(filled.symbol)
                self.enqueue_audit(
                    "ORDER_FILLED",
                    {
                        "side": filled.side.value,
                        "qty": filled.qty,
                        "filled_price": fill_price,
                        "price_reference": price,
                        "fee": estimated_fee,
                        "commission": estimated_fee,
                        "slippage_pct_vs_signal": slippage_pct_vs_signal,
                        "status": filled.status.value,
                        "currency": currency,
                    },
                    symbol=filled.symbol,
                    strategy=signal.strategy_name,
                )
                if self._on_fill_received:
                    self._on_fill_received(filled)
            else:
                logger.warning(
                    f"Order {filled.status.value}: "
                    f"{filled.side.value.upper()} {filled.qty} {filled.symbol}"
                )
                self.enqueue_audit(
                    "ORDER_NOT_FILLED",
                    {
                        "side": filled.side.value,
                        "qty": filled.qty,
                        "status": filled.status.value,
                    },
                    symbol=filled.symbol,
                    strategy=signal.strategy_name,
                    severity="warning",
                )
                if filled.side.value == "sell":
                    self.risk.record_trade_result(is_profitable=False)
        except Exception as exc:
            logger.error("Order submission failed: %s", exc)
            self.enqueue_audit(
                "ORDER_ERROR",
                {"error": str(exc)},
                symbol=order.symbol,
                strategy=signal.strategy_name,
                severity="error",
            )

    def _update_var(self, bar: Bar) -> None:
        try:
            current_value = run_broker_operation(
                self.settings,
                "get_portfolio_value",
                self.broker.get_portfolio_value,
                retry_state=self.broker_retry_state,
                kill_switch=self.kill_switch,
                enqueue_audit=self.enqueue_audit,
                symbol=bar.symbol,
                strategy=self.settings.strategy.name,
            )
        except RuntimeError as exc:
            logger.error("Broker unavailable during VaR update: %s", exc)
            return

        if self.prev_portfolio_value > 0:
            daily_return = (current_value - self.prev_portfolio_value) / self.prev_portfolio_value
            self.risk.update_portfolio_return(daily_return)
        self.prev_portfolio_value = current_value

    def _snapshot_portfolio(self, bar: Bar) -> None:
        """Fetch positions/cash and generate portfolio snapshot."""
        symbol_currencies = None
        cash_currency = self.settings.base_currency
        if self.settings.broker.provider.lower() == "ibkr":
            try:
                positions = run_broker_operation(
                    self.settings,
                    "get_positions",
                    self.broker.get_positions,
                    retry_state=self.broker_retry_state,
                    kill_switch=self.kill_switch,
                    enqueue_audit=self.enqueue_audit,
                    symbol=bar.symbol,
                    strategy=self.settings.strategy.name,
                )
            except RuntimeError as exc:
                logger.error("Broker unavailable during snapshot positions: %s", exc)
                return
            symbol_currencies = {
                sym: self.broker.get_symbol_currency(sym) for sym in positions.keys()
            }
            cash_currency = (
                run_broker_operation(
                    self.settings,
                    "get_account_base_currency",
                    self.broker.get_account_base_currency,
                    retry_state=self.broker_retry_state,
                    kill_switch=self.kill_switch,
                    enqueue_audit=self.enqueue_audit,
                    symbol=bar.symbol,
                    strategy=self.settings.strategy.name,
                )
                or self.settings.base_currency
            )
            snap = self.tracker.snapshot(
                positions,
                run_broker_operation(
                    self.settings,
                    "get_cash",
                    self.broker.get_cash,
                    retry_state=self.broker_retry_state,
                    kill_switch=self.kill_switch,
                    enqueue_audit=self.enqueue_audit,
                    symbol=bar.symbol,
                    strategy=self.settings.strategy.name,
                ),
                base_currency=self.settings.base_currency,
                symbol_currencies=symbol_currencies,
                cash_currency=cash_currency,
                fx_rates=self.settings.fx_rates,
            )
        else:
            snap = self.tracker.snapshot(
                run_broker_operation(
                    self.settings,
                    "get_positions",
                    self.broker.get_positions,
                    retry_state=self.broker_retry_state,
                    kill_switch=self.kill_switch,
                    enqueue_audit=self.enqueue_audit,
                    symbol=bar.symbol,
                    strategy=self.settings.strategy.name,
                ),
                run_broker_operation(
                    self.settings,
                    "get_cash",
                    self.broker.get_cash,
                    retry_state=self.broker_retry_state,
                    kill_switch=self.kill_switch,
                    enqueue_audit=self.enqueue_audit,
                    symbol=bar.symbol,
                    strategy=self.settings.strategy.name,
                ),
                base_currency=self.settings.base_currency,
                cash_currency=cash_currency,
                fx_rates=self.settings.fx_rates,
            )
        logger.info(
            f"Portfolio: ${snap['portfolio_value']:,.2f}  "
            f"cash=${snap['cash']:,.2f}  "
            f"positions={snap['num_positions']}  "
            f"return={snap['return_pct']:+.2f}%"
        )
