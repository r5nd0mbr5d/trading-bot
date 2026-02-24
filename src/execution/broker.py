"""Broker interface layer.

BrokerBase  — abstract interface (implement this to add new brokers)
AlpacaBroker — Alpaca Markets adapter (paper trading is free)
PaperBroker  — in-memory simulation used by BacktestEngine

To add Interactive Brokers: implement BrokerBase using ib_insync.
To add Binance (crypto):    implement BrokerBase using python-binance.
"""

import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict

from src.data.models import Order, OrderSide, OrderStatus, Position

logger = logging.getLogger(__name__)


class BrokerBase(ABC):
    @abstractmethod
    def submit_order(self, order: Order) -> Order: ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool: ...

    @abstractmethod
    def get_positions(self) -> Dict[str, Position]: ...

    @abstractmethod
    def get_portfolio_value(self) -> float: ...

    @abstractmethod
    def get_cash(self) -> float: ...


class AlpacaBroker(BrokerBase):
    """
    Alpaca Markets adapter — paper trading is completely free.

    Setup:
      1. Create a free account at https://alpaca.markets
      2. Under "Paper Trading" generate API keys
      3. Copy keys to .env:  ALPACA_API_KEY=...  ALPACA_SECRET_KEY=...
      4. pip install alpaca-py
    """

    def __init__(self, settings):
        self.cfg = settings.broker
        self._client = None
        self._connect()

    def _connect(self):
        try:
            from alpaca.trading.client import TradingClient

            self._client = TradingClient(
                self.cfg.api_key,
                self.cfg.secret_key,
                paper=self.cfg.paper_trading,
            )
            mode = "paper" if self.cfg.paper_trading else "LIVE"
            logger.info(f"Connected to Alpaca ({mode})")
        except ImportError:
            logger.warning("alpaca-py not installed: pip install alpaca-py")
        except Exception as e:
            logger.error(f"Alpaca connection failed: {e}")

    def submit_order(self, order: Order) -> Order:
        if not self._client:
            order.status = OrderStatus.REJECTED
            return order
        try:
            from alpaca.trading.enums import OrderSide as AS
            from alpaca.trading.enums import TimeInForce
            from alpaca.trading.requests import MarketOrderRequest

            req = MarketOrderRequest(
                symbol=order.symbol,
                qty=order.qty,
                side=AS.BUY if order.side == OrderSide.BUY else AS.SELL,
                time_in_force=TimeInForce.DAY,
            )
            resp = self._client.submit_order(req)
            order.order_id = str(resp.id)
            order.status = OrderStatus.PENDING
            logger.info(f"Submitted: {order.side.value} {order.qty} {order.symbol}")
        except Exception as e:
            logger.error(f"submit_order failed: {e}")
            order.status = OrderStatus.REJECTED
        return order

    def cancel_order(self, order_id: str) -> bool:
        if not self._client:
            return False
        try:
            self._client.cancel_order_by_id(order_id)
            return True
        except Exception as e:
            logger.error(f"cancel_order failed: {e}")
            return False

    def get_positions(self) -> Dict[str, Position]:
        if not self._client:
            return {}
        try:
            return {
                p.symbol: Position(
                    symbol=p.symbol,
                    qty=float(p.qty),
                    avg_entry_price=float(p.avg_entry_price),
                    current_price=float(p.current_price),
                )
                for p in self._client.get_all_positions()
            }
        except Exception as e:
            logger.error(f"get_positions failed: {e}")
            return {}

    def get_portfolio_value(self) -> float:
        if not self._client:
            return 0.0
        try:
            return float(self._client.get_account().portfolio_value)
        except Exception as e:
            logger.error(f"get_portfolio_value failed: {e}")
            return 0.0

    def get_cash(self) -> float:
        if not self._client:
            return 0.0
        try:
            return float(self._client.get_account().cash)
        except Exception as e:
            logger.error(f"get_cash failed: {e}")
            return 0.0

    def is_paper_mode(self) -> bool:
        if self._client is None:
            return bool(self.cfg.paper_trading)
        for attr in ("paper", "_paper"):
            value = getattr(self._client, attr, None)
            if value is not None:
                return bool(value)
        return bool(self.cfg.paper_trading)

    def is_live_mode(self) -> bool:
        return not self.is_paper_mode()


class PaperBroker(BrokerBase):
    """
    Purely in-memory paper broker — no external connections.
    Used exclusively by BacktestEngine. Instant fills at close price.
    """

    def __init__(self, initial_cash: float = 100_000.0):
        self._cash = initial_cash
        self._positions: Dict[str, Position] = {}
        self._current_prices: Dict[str, float] = {}

    def update_prices(self, prices: Dict[str, float]) -> None:
        """Call once per bar so positions track current market value."""
        self._current_prices.update(prices)
        for sym, pos in self._positions.items():
            if sym in prices:
                pos.current_price = prices[sym]

    def submit_order(self, order: Order) -> Order:
        order.order_id = str(uuid.uuid4())
        price = self._current_prices.get(order.symbol)

        if not price:
            order.status = OrderStatus.REJECTED
            return order

        cost = order.qty * price

        if order.side == OrderSide.BUY:
            if cost > self._cash:
                order.status = OrderStatus.REJECTED
                return order
            self._cash -= cost
            if order.symbol in self._positions:
                pos = self._positions[order.symbol]
                new_qty = pos.qty + order.qty
                pos.avg_entry_price = (pos.qty * pos.avg_entry_price + cost) / new_qty
                pos.qty = new_qty
            else:
                self._positions[order.symbol] = Position(
                    symbol=order.symbol,
                    qty=order.qty,
                    avg_entry_price=price,
                    current_price=price,
                )
        else:  # SELL
            if order.symbol not in self._positions:
                order.status = OrderStatus.REJECTED
                return order
            pos = self._positions[order.symbol]
            fill_qty = min(order.qty, pos.qty)
            self._cash += fill_qty * price
            pos.qty -= fill_qty
            if pos.qty <= 0:
                del self._positions[order.symbol]

        order.status = OrderStatus.FILLED
        order.filled_price = price
        order.filled_at = datetime.now(timezone.utc)
        return order

    def fill_order_at_price(
        self, order: Order, fill_price: float, commission: float = 0.0
    ) -> Order:
        """
        Fill an order at an explicit price (used by BacktestEngine for
        next-bar open fills with slippage already baked into fill_price).
        Commission is deducted from cash on both buys and sells.
        """
        order.order_id = str(uuid.uuid4())

        if fill_price <= 0:
            order.status = OrderStatus.REJECTED
            return order

        cost = order.qty * fill_price

        if order.side == OrderSide.BUY:
            total_cost = cost + commission
            if total_cost > self._cash:
                order.status = OrderStatus.REJECTED
                return order
            self._cash -= total_cost
            if order.symbol in self._positions:
                pos = self._positions[order.symbol]
                new_qty = pos.qty + order.qty
                pos.avg_entry_price = (pos.qty * pos.avg_entry_price + cost) / new_qty
                pos.qty = new_qty
                pos.current_price = fill_price
            else:
                self._positions[order.symbol] = Position(
                    symbol=order.symbol,
                    qty=order.qty,
                    avg_entry_price=fill_price,
                    current_price=fill_price,
                )
        else:  # SELL
            if order.symbol not in self._positions:
                order.status = OrderStatus.REJECTED
                return order
            pos = self._positions[order.symbol]
            fill_qty = min(order.qty, pos.qty)
            self._cash += fill_qty * fill_price - commission
            pos.qty -= fill_qty
            if pos.qty <= 0:
                del self._positions[order.symbol]

        order.status = OrderStatus.FILLED
        order.filled_price = fill_price
        order.filled_at = datetime.now(timezone.utc)
        return order

    def cancel_order(self, order_id: str) -> bool:
        return False  # Instant fills — nothing to cancel

    def get_positions(self) -> Dict[str, Position]:
        return dict(self._positions)

    def get_portfolio_value(self) -> float:
        market_value = sum(p.market_value for p in self._positions.values())
        return self._cash + market_value

    def get_cash(self) -> float:
        return self._cash
