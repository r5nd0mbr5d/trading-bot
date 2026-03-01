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
from decimal import Decimal, InvalidOperation
from typing import Any, Dict

from src.data.models import Order, OrderSide, OrderStatus, Position
from src.data.symbol_utils import normalize_symbol

logger = logging.getLogger(__name__)


class BrokerConnectionError(RuntimeError):
    """Raised when a broker cannot be connected/initialised."""


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
                symbol=normalize_symbol(order.symbol, "alpaca"),
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


class BinanceBroker(BrokerBase):
    """Binance broker adapter (spot) with optional testnet routing."""

    def __init__(self, settings):
        self.cfg = settings.broker
        self._client = None
        self._order_symbol_by_id: Dict[str, str] = {}
        self._connect()

    def _connect(self) -> None:
        try:
            from binance.client import Client

            self._client = Client(
                self.cfg.binance_api_key,
                self.cfg.binance_secret_key,
                testnet=self.cfg.binance_testnet,
            )
            if self.cfg.binance_testnet:
                self._client.API_URL = "https://testnet.binance.vision/api"
            logger.info(
                "Connected to Binance (%s)",
                "testnet" if self.cfg.binance_testnet else "live",
            )
        except ImportError:
            logger.warning("python-binance not installed: pip install python-binance")
            self._client = None
        except Exception as exc:
            logger.error("Binance connection failed: %s", exc)
            self._client = None

    def _round_quantity(self, symbol: str, quantity: float) -> float:
        if self._client is None:
            return 0.0
        try:
            symbol_info = self._client.get_symbol_info(symbol) or {}
            filters = symbol_info.get("filters", []) or []
            lot_filter = next((flt for flt in filters if flt.get("filterType") == "LOT_SIZE"), None)
            if lot_filter is None:
                return max(0.0, round(float(quantity), 8))

            step_size = str(lot_filter.get("stepSize", "0"))
            min_qty = float(lot_filter.get("minQty", "0") or 0.0)
            if float(quantity) < min_qty:
                return 0.0

            step = Decimal(step_size)
            if step <= 0:
                return max(0.0, round(float(quantity), 8))

            qty_dec = Decimal(str(max(float(quantity), 0.0)))
            rounded_qty = (qty_dec // step) * step
            if rounded_qty < Decimal(str(min_qty)):
                return 0.0
            return float(rounded_qty)
        except (InvalidOperation, ValueError, TypeError):
            return max(0.0, round(float(quantity), 8))
        except Exception as exc:
            logger.error("Binance quantity rounding failed for %s: %s", symbol, exc)
            return max(0.0, round(float(quantity), 8))

    def _symbol_price(self, symbol: str) -> float:
        if not self._client:
            return 0.0
        try:
            ticker = self._client.get_symbol_ticker(symbol=symbol)
            return float(ticker.get("price", 0.0) or 0.0)
        except Exception:
            return 0.0

    def submit_order(self, order: Order) -> Order:
        if not self._client:
            order.status = OrderStatus.REJECTED
            return order

        try:
            symbol = normalize_symbol(order.symbol, "binance")
            qty = self._round_quantity(symbol, order.qty)
            if qty <= 0:
                order.status = OrderStatus.REJECTED
                return order

            if order.side == OrderSide.BUY:
                response: Dict[str, Any] = self._client.order_market_buy(
                    symbol=symbol, quantity=qty
                )
            else:
                response = self._client.order_market_sell(symbol=symbol, quantity=qty)

            order_id = str(response.get("orderId", ""))
            order.order_id = order_id
            if order_id:
                self._order_symbol_by_id[order_id] = symbol

            status = str(response.get("status", "")).upper()
            order.status = OrderStatus.FILLED if status == "FILLED" else OrderStatus.PENDING

            fills = response.get("fills", []) or []
            if fills:
                total_qty = 0.0
                weighted_notional = 0.0
                for fill in fills:
                    fill_qty = float(fill.get("qty", 0.0) or 0.0)
                    fill_price = float(fill.get("price", 0.0) or 0.0)
                    total_qty += fill_qty
                    weighted_notional += fill_qty * fill_price
                if total_qty > 0:
                    order.filled_price = weighted_notional / total_qty
                    order.filled_at = datetime.now(timezone.utc)

            return order
        except Exception as exc:
            logger.error("Binance submit_order failed: %s", exc)
            order.status = OrderStatus.REJECTED
            return order

    def cancel_order(self, order_id: str) -> bool:
        if not self._client:
            return False

        symbol = self._order_symbol_by_id.get(str(order_id), "")
        if not symbol:
            return False

        try:
            self._client.cancel_order(symbol=symbol, orderId=int(order_id))
            return True
        except Exception as exc:
            logger.error("Binance cancel_order failed: %s", exc)
            return False

    def get_positions(self) -> Dict[str, Position]:
        if not self._client:
            return {}

        positions: Dict[str, Position] = {}
        try:
            account = self._client.get_account() or {}
            balances = account.get("balances", []) or []
            for balance in balances:
                asset = str(balance.get("asset", "")).upper()
                free_qty = float(balance.get("free", 0.0) or 0.0)
                locked_qty = float(balance.get("locked", 0.0) or 0.0)
                total_qty = free_qty + locked_qty
                if asset in {"", "GBP"} or total_qty <= 0:
                    continue

                symbol = normalize_symbol(f"{asset}GBP", "binance")
                mark_price = self._symbol_price(symbol)
                if mark_price <= 0:
                    continue

                positions[symbol] = Position(
                    symbol=symbol,
                    qty=total_qty,
                    avg_entry_price=mark_price,
                    current_price=mark_price,
                )
            return positions
        except Exception as exc:
            logger.error("Binance get_positions failed: %s", exc)
            return {}

    def get_portfolio_value(self) -> float:
        if not self._client:
            return 0.0

        try:
            account = self._client.get_account() or {}
            balances = account.get("balances", []) or []
            total_value = 0.0

            for balance in balances:
                asset = str(balance.get("asset", "")).upper()
                free_qty = float(balance.get("free", 0.0) or 0.0)
                locked_qty = float(balance.get("locked", 0.0) or 0.0)
                total_qty = free_qty + locked_qty
                if total_qty <= 0:
                    continue

                if asset == "GBP":
                    total_value += total_qty
                    continue

                symbol = normalize_symbol(f"{asset}GBP", "binance")
                mark_price = self._symbol_price(symbol)
                if mark_price > 0:
                    total_value += total_qty * mark_price

            return total_value
        except Exception as exc:
            logger.error("Binance get_portfolio_value failed: %s", exc)
            return 0.0

    def get_cash(self) -> float:
        if not self._client:
            return 0.0

        try:
            account = self._client.get_account() or {}
            balances = account.get("balances", []) or []
            gbp_balance = next(
                (balance for balance in balances if str(balance.get("asset", "")).upper() == "GBP"),
                None,
            )
            if gbp_balance is None:
                return 0.0
            return float(gbp_balance.get("free", 0.0) or 0.0)
        except Exception as exc:
            logger.error("Binance get_cash failed: %s", exc)
            return 0.0


class CoinbaseBroker(BrokerBase):
    """Coinbase Advanced Trade broker adapter with optional sandbox routing."""

    def __init__(self, settings):
        self.cfg = settings.broker
        self._client = None
        self._order_symbol_by_id: Dict[str, str] = {}
        self._connect()

    def _connect(self) -> None:
        try:
            from coinbase.rest import RESTClient

            base_url = (
                "https://api-public.sandbox.exchange.coinbase.com"
                if self.cfg.coinbase_sandbox
                else "https://api.coinbase.com"
            )
            self._client = RESTClient(
                api_key=self.cfg.coinbase_api_key_id,
                api_secret=self.cfg.coinbase_private_key,
                base_url=base_url,
            )
            logger.info(
                "Connected to Coinbase Advanced Trade (%s)",
                "sandbox" if self.cfg.coinbase_sandbox else "live",
            )
        except ImportError:
            logger.warning("coinbase-advanced-py not installed: pip install coinbase-advanced-py")
            self._client = None
            raise BrokerConnectionError("coinbase-advanced-py is not installed")
        except Exception as exc:
            logger.error("Coinbase connection failed: %s", exc)
            self._client = None
            raise BrokerConnectionError(str(exc)) from exc

    @staticmethod
    def _to_dict(payload: Any) -> Dict[str, Any]:
        if payload is None:
            return {}
        if isinstance(payload, dict):
            return payload
        if hasattr(payload, "to_dict"):
            converted = payload.to_dict()
            if isinstance(converted, dict):
                return converted
        if hasattr(payload, "__dict__"):
            return dict(payload.__dict__)
        return {}

    def submit_order(self, order: Order) -> Order:
        if not self._client:
            order.status = OrderStatus.REJECTED
            return order

        try:
            product_id = normalize_symbol(order.symbol, "coinbase")
            qty = max(float(order.qty), 0.0)
            if qty <= 0:
                order.status = OrderStatus.REJECTED
                return order

            client_order_id = str(uuid.uuid4())
            if order.side == OrderSide.BUY:
                response = self._client.market_order_buy(
                    client_order_id=client_order_id,
                    product_id=product_id,
                    base_size=str(qty),
                )
            else:
                response = self._client.market_order_sell(
                    client_order_id=client_order_id,
                    product_id=product_id,
                    base_size=str(qty),
                )

            payload = self._to_dict(response)
            order_id = str(
                payload.get("order_id")
                or payload.get("id")
                or payload.get("success_response", {}).get("order_id", "")
            )
            order.order_id = order_id
            if order_id:
                self._order_symbol_by_id[order_id] = product_id

            status = str(payload.get("status") or payload.get("order_status") or "").upper()
            if status in {"FILLED", "DONE"}:
                order.status = OrderStatus.FILLED
            elif status in {"OPEN", "PENDING", "PENDING_NEW"}:
                order.status = OrderStatus.PENDING
            elif status in {"CANCELLED", "CANCELED"}:
                order.status = OrderStatus.CANCELLED
            elif status:
                order.status = OrderStatus.PENDING
            else:
                order.status = OrderStatus.PENDING

            filled_price = payload.get("filled_price") or payload.get("average_filled_price")
            if filled_price is not None:
                order.filled_price = float(filled_price)
                order.filled_at = datetime.now(timezone.utc)

            return order
        except Exception as exc:
            logger.error("Coinbase submit_order failed: %s", exc)
            order.status = OrderStatus.REJECTED
            return order

    def cancel_order(self, order_id: str) -> bool:
        if not self._client:
            return False
        try:
            response = self._client.cancel_orders(order_ids=[order_id])
            payload = self._to_dict(response)
            if "results" in payload and isinstance(payload["results"], list):
                return any(
                    str(result.get("success", "")).lower() == "true"
                    for result in payload["results"]
                )
            return True
        except Exception as exc:
            logger.error("Coinbase cancel_order failed: %s", exc)
            return False

    def _product_price(self, product_id: str) -> float:
        if not self._client:
            return 0.0
        try:
            product = self._client.get_product(product_id=product_id)
            payload = self._to_dict(product)
            value = (
                payload.get("price") or payload.get("last_price") or payload.get("mid_market_price")
            )
            return float(value or 0.0)
        except Exception:
            return 0.0

    def get_positions(self) -> Dict[str, Position]:
        if not self._client:
            return {}

        try:
            response = self._client.get_accounts()
            payload = self._to_dict(response)
            accounts = payload.get("accounts", []) or payload.get("data", []) or []
            positions: Dict[str, Position] = {}

            for account in accounts:
                currency = str(account.get("currency") or account.get("asset") or "").upper()
                if currency in {"", "GBP"}:
                    continue

                available = float(account.get("available_balance", {}).get("value", 0.0) or 0.0)
                hold = float(account.get("hold", {}).get("value", 0.0) or 0.0)
                qty = available + hold
                if qty <= 0:
                    continue

                product_id = normalize_symbol(f"{currency}GBP", "coinbase")
                mark_price = self._product_price(product_id)
                if mark_price <= 0:
                    continue

                positions[product_id] = Position(
                    symbol=product_id,
                    qty=qty,
                    avg_entry_price=mark_price,
                    current_price=mark_price,
                )
            return positions
        except Exception as exc:
            logger.error("Coinbase get_positions failed: %s", exc)
            return {}

    def get_portfolio_value(self) -> float:
        if not self._client:
            return 0.0

        try:
            response = self._client.get_accounts()
            payload = self._to_dict(response)
            accounts = payload.get("accounts", []) or payload.get("data", []) or []
            total_value = 0.0

            for account in accounts:
                currency = str(account.get("currency") or account.get("asset") or "").upper()
                available = float(account.get("available_balance", {}).get("value", 0.0) or 0.0)
                hold = float(account.get("hold", {}).get("value", 0.0) or 0.0)
                qty = available + hold
                if qty <= 0:
                    continue

                if currency == "GBP":
                    total_value += qty
                    continue

                product_id = normalize_symbol(f"{currency}GBP", "coinbase")
                mark_price = self._product_price(product_id)
                if mark_price > 0:
                    total_value += qty * mark_price

            return total_value
        except Exception as exc:
            logger.error("Coinbase get_portfolio_value failed: %s", exc)
            return 0.0

    def get_cash(self) -> float:
        if not self._client:
            return 0.0

        try:
            response = self._client.get_accounts()
            payload = self._to_dict(response)
            accounts = payload.get("accounts", []) or payload.get("data", []) or []
            gbp_account = next(
                (
                    account
                    for account in accounts
                    if str(account.get("currency") or account.get("asset") or "").upper() == "GBP"
                ),
                None,
            )
            if gbp_account is None:
                return 0.0
            return float(gbp_account.get("available_balance", {}).get("value", 0.0) or 0.0)
        except Exception as exc:
            logger.error("Coinbase get_cash failed: %s", exc)
            return 0.0


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
