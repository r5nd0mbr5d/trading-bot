"""Risk Management Module.

Implements the guard layer between strategy signals and order submission.
Every signal must pass through here before becoming an order.

Enterprise risk controls implemented:
  - Fixed-fractional position sizing (risk fixed % of portfolio per trade)
  - Maximum position size cap (% of portfolio)
  - Maximum open positions limit
  - Drawdown circuit breaker (halt trading if portfolio falls too far)
  - Intraday loss circuit breaker (halt if portfolio drops >X% same day)
  - Consecutive loss circuit breaker (halt after N losing trades)
    - Sector concentration gate (max % of portfolio per sector)
  - Stop-loss and take-profit attachment
  - Paper-trading guardrails (order limits, reject tracking, session windows)

To add:
    - Correlation exposure limit
  - Slippage model
"""

import json
import logging
import math
import threading
from datetime import date as _Date
from pathlib import Path
from typing import Dict, Optional

from config.settings import Settings
from src.data.models import Order, OrderSide, Position, Signal, SignalType
from src.risk.paper_guardrails import PaperGuardrails
from src.risk.var import PortfolioVaR

logger = logging.getLogger(__name__)


def _normalize_symbol(symbol: str) -> str:
    return (symbol or "").upper()


def _load_sector_map(path: str) -> Dict[str, str]:
    if not path:
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Sector map load failed (%s): %s", path, exc)
        return {}

    baskets = payload.get("baskets", {}) if isinstance(payload, dict) else {}
    sector_map: Dict[str, str] = {}
    for basket in baskets.values():
        if not isinstance(basket, dict):
            continue
        basket_sector = str(basket.get("sector") or "").strip()
        symbol_details = basket.get("symbol_details", {}) or {}
        if isinstance(symbol_details, dict):
            for sym, details in symbol_details.items():
                if not isinstance(details, dict):
                    continue
                sector = str(details.get("sector") or "").strip()
                if sector:
                    sector_map[_normalize_symbol(sym)] = sector

        if basket_sector:
            for sym in basket.get("symbols", []) or []:
                norm = _normalize_symbol(sym)
                if norm and norm not in sector_map:
                    sector_map[norm] = basket_sector

    return sector_map


class RiskManager:

    def __init__(self, settings: Settings):
        self.cfg = settings.risk
        self._peak_value: float = settings.initial_capital
        self._lock = threading.Lock()

        # Paper-trading guardrails (only active when paper_trading=True)
        self._paper_guardrails = PaperGuardrails(settings.paper_guardrails)
        self._is_paper_mode = settings.broker.paper_trading

        # Intraday loss tracking
        self._intraday_start_value: Optional[float] = None
        self._intraday_date: Optional[_Date] = None

        # Consecutive loss tracking
        self._consecutive_losses: int = 0

        # Portfolio VaR gate
        self._portfolio_var = PortfolioVaR(
            window=self.cfg.var_window,
        )
        self._sector_map = _load_sector_map(self.cfg.sector_map_path)
        self._last_rejection_code: str = ""
        self._last_rejection_reason: str = ""

    def get_last_rejection(self) -> Dict[str, str]:
        return {
            "code": self._last_rejection_code,
            "reason": self._last_rejection_reason,
        }

    def update_portfolio_return(self, daily_return: float) -> None:
        """
        Feed today's portfolio return into the VaR tracker.
        Call once per bar from the engine after equity-curve valuation.
        """
        self._portfolio_var.update(daily_return)

    def record_trade_result(self, is_profitable: bool) -> None:
        """
        Call after each closed trade to update the consecutive-loss counter.
        A profitable trade resets the counter; a loss increments it.
        """
        if is_profitable:
            self._consecutive_losses = 0
        else:
            self._consecutive_losses += 1

    def approve_signal(
        self,
        signal: Signal,
        portfolio_value: float,
        current_price: float,
        open_positions: Dict[str, Position],
    ) -> Optional[Order]:
        """
        Validate a signal against all risk rules.
        Returns an Order if approved, None if rejected.
        """
        self._last_rejection_code = ""
        self._last_rejection_reason = ""

        # --- Thread-safe peak drawdown circuit breaker ---
        with self._lock:
            self._peak_value = max(self._peak_value, portfolio_value)
            drawdown = 0.0
            if self._peak_value > 0:
                drawdown = (self._peak_value - portfolio_value) / self._peak_value

        if drawdown > self.cfg.max_drawdown_pct:
            logger.warning(
                f"CIRCUIT BREAKER [drawdown]: {drawdown:.1%} exceeds "
                f"limit {self.cfg.max_drawdown_pct:.1%}. Trading halted."
            )
            return None

        # --- Intraday loss circuit breaker ---
        signal_date = signal.timestamp.date()
        if self._intraday_date != signal_date:
            # New trading day — reset intraday tracking
            self._intraday_date = signal_date
            self._intraday_start_value = portfolio_value

        if self._intraday_start_value and self._intraday_start_value > 0:
            intraday_loss = (
                self._intraday_start_value - portfolio_value
            ) / self._intraday_start_value
            if intraday_loss > self.cfg.max_intraday_loss_pct:
                logger.warning(
                    f"CIRCUIT BREAKER [intraday]: loss {intraday_loss:.1%} exceeds "
                    f"limit {self.cfg.max_intraday_loss_pct:.1%}. Halted for today."
                )
                return None

        # --- Consecutive loss circuit breaker ---
        if self._consecutive_losses >= self.cfg.consecutive_loss_limit:
            logger.warning(
                f"CIRCUIT BREAKER [consecutive losses]: {self._consecutive_losses} "
                f"consecutive losses (limit {self.cfg.consecutive_loss_limit}). "
                f"Trading halted."
            )
            return None

        # --- Portfolio VaR gate ---
        if not self._portfolio_var.is_within_limit(self.cfg.max_var_pct):
            logger.warning(
                f"RISK GATE [VaR]: current VaR95={self._portfolio_var.var95:.2%} "
                f"exceeds limit {self.cfg.max_var_pct:.2%}. Order rejected."
            )
            return None

        # --- Paper-trading guardrails (only in paper mode, not backtest) ---
        if self._is_paper_mode:
            guardrail_reasons = self._paper_guardrails.all_checks(signal.symbol)
            if guardrail_reasons:
                reason_str = "; ".join(guardrail_reasons)
                logger.warning(f"PAPER GUARDRAIL [signal rejected]: {reason_str}")
                # Log as audit event that guardrail blocked this signal
                for reason in guardrail_reasons:
                    logger.debug(f"Guardrail block: {reason}")
                return None

        if signal.signal_type == SignalType.CLOSE:
            return self._build_close_order(signal, open_positions)

        if signal.signal_type == SignalType.LONG:
            return self._build_buy_order(signal, portfolio_value, current_price, open_positions)

        return None

    def _build_close_order(
        self, signal: Signal, open_positions: Dict[str, Position]
    ) -> Optional[Order]:
        if signal.symbol not in open_positions:
            return None
        pos = open_positions[signal.symbol]
        return Order(symbol=signal.symbol, side=OrderSide.SELL, qty=pos.qty)

    def _build_buy_order(
        self,
        signal: Signal,
        portfolio_value: float,
        price: float,
        open_positions: Dict[str, Position],
    ) -> Optional[Order]:
        if signal.symbol in open_positions:
            logger.debug(f"Already holding {signal.symbol}, skipping")
            return None

        if len(open_positions) >= self.cfg.max_open_positions:
            logger.info(
                f"Max open positions ({self.cfg.max_open_positions}) reached, "
                f"skipping {signal.symbol}"
            )
            return None

        # --- ATR-based stops (preferred) or fall back to fixed % ---
        atr = signal.metadata.get("atr") if signal.metadata else None
        if self.cfg.use_atr_stops and atr and atr > 0 and price > 0:
            stop_loss = round(max(price - self.cfg.atr_multiplier * atr, 0.0001), 4)
            take_profit = round(price + self.cfg.atr_tp_multiplier * atr, 4)
            # Effective stop % for position sizing (replaces fixed stop_loss_pct)
            effective_stop_pct = (price - stop_loss) / price
            logger.debug(
                f"ATR stop for {signal.symbol}: entry=${price:.2f}  "
                f"ATR={atr:.4f}  stop=${stop_loss:.4f} ({effective_stop_pct:.1%})  "
                f"TP=${take_profit:.4f}"
            )
        else:
            stop_loss = round(price * (1 - self.cfg.stop_loss_pct), 4)
            take_profit = round(price * (1 + self.cfg.take_profit_pct), 4)
            effective_stop_pct = self.cfg.stop_loss_pct

        qty = self._size_position(portfolio_value, price, signal.strength, effective_stop_pct)
        if qty <= 0:
            return None

        if reason := self._check_sector_concentration(
            signal.symbol,
            open_positions,
            portfolio_value,
            qty * price,
        ):
            logger.warning("RISK GATE [sector]: %s", reason)
            self._last_rejection_code = "SECTOR_CONCENTRATION_REJECTED"
            self._last_rejection_reason = reason
            return None

        return Order(
            symbol=signal.symbol,
            side=OrderSide.BUY,
            qty=qty,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    def _size_position(
        self,
        portfolio_value: float,
        price: float,
        signal_strength: float = 1.0,
        stop_pct: Optional[float] = None,
    ) -> float:
        """
        Fixed-fractional sizing:
          risk_dollars = portfolio * max_portfolio_risk_pct * signal_strength
          qty          = risk_dollars / (price * stop_pct)

        stop_pct defaults to the configured stop_loss_pct, but is overridden
        by the ATR-derived stop distance when ATR stops are active.

        Capped at max_position_pct of portfolio.
        Alpaca supports fractional shares so qty can be non-integer.
        """
        effective_stop = stop_pct if stop_pct is not None else self.cfg.stop_loss_pct
        if not math.isfinite(price) or not math.isfinite(effective_stop):
            return 0.0
        if price <= 0 or effective_stop <= 0:
            return 0.0
        if not math.isfinite(portfolio_value) or portfolio_value <= 0:
            return 0.0
        if not math.isfinite(signal_strength):
            return 0.0
        signal_strength = max(0.0, min(1.0, signal_strength))

        risk_dollars = portfolio_value * self.cfg.max_portfolio_risk_pct * signal_strength
        qty_from_risk = risk_dollars / (price * effective_stop)
        qty_from_cap = (portfolio_value * self.cfg.max_position_pct) / price
        qty = min(qty_from_risk, qty_from_cap)
        return max(0.0, round(qty, 4))

    def _check_sector_concentration(
        self,
        symbol: str,
        open_positions: Dict[str, Position],
        portfolio_value: float,
        new_position_value: float,
    ) -> str:
        if self.cfg.skip_sector_concentration:
            return ""
        if portfolio_value <= 0 or new_position_value <= 0:
            return ""
        if not self._sector_map:
            return ""

        sector = self._sector_map.get(_normalize_symbol(symbol))
        if not sector:
            return ""

        sector_value = 0.0
        for sym, pos in open_positions.items():
            if self._sector_map.get(_normalize_symbol(sym)) == sector:
                sector_value += pos.market_value

        projected_pct = (sector_value + new_position_value) / portfolio_value
        if projected_pct > self.cfg.max_sector_concentration_pct:
            return (
                f"{sector} would be {projected_pct:.1%} "
                f"(limit {self.cfg.max_sector_concentration_pct:.1%})"
            )
        return ""

    # ========== Paper Guardrails Tracking ==========
    def record_order_submitted(self) -> None:
        """
        Record that an order was submitted (passed all risk gates).
        Called from main.py after RiskManager.approve_signal() returns an Order.
        Only applicable in paper trading mode; no-op otherwise.
        """
        if self._is_paper_mode:
            self._paper_guardrails.record_order()

    def record_signal_rejected(self, symbol: str) -> None:
        """
        Record that a signal was explicitly rejected by the user or due to
        soft constraints (e.g., reject rate limit). Increments consecutive
        reject counter and sets per-symbol cooldown.
        """
        if self._is_paper_mode:
            self._paper_guardrails.record_reject(symbol)

    def record_signal_filled(self) -> None:
        """
        Record that a signal's resulting order was filled. Breaks the consecutive
        reject streak, signaling that execution is working cleanly.
        Called from main.py after a fill event is processed.
        """
        if self._is_paper_mode:
            self._paper_guardrails.reset_reject_counter()
