"""Interactive Brokers adapter.

Requires TWS or IB Gateway running locally and `ib_insync` installed.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Any

from src.data.models import Order, OrderSide, OrderStatus, Position
from src.execution.broker import BrokerBase

logger = logging.getLogger(__name__)


class IBKRBroker(BrokerBase):
    """Broker adapter for Interactive Brokers via ib_insync."""

    def __init__(self, settings):
        self.cfg = settings.broker
        self._ib = None
        self._Stock = None
        self._MarketOrder = None
        self._symbol_currency_cache: Dict[str, str] = {}
        self._connect()

    def _connect(self) -> None:
        try:
            from ib_insync import IB, MarketOrder, Stock, util

            util.patchAsyncio()

            self._ib = IB()
            self._Stock = Stock
            self._MarketOrder = MarketOrder

            # Try to connect with configured clientId, or use alternative if already in use
            client_id = self.cfg.ibkr_client_id
            max_attempts = 5
            attempt = 0

            while attempt < max_attempts:
                try:
                    self._ib.connect(
                        host=self.cfg.ibkr_host,
                        port=self.cfg.ibkr_port,
                        clientId=client_id,
                        timeout=5,
                    )
                    logger.info(
                        "Connected to IBKR at %s:%s (clientId=%s)",
                        self.cfg.ibkr_host,
                        self.cfg.ibkr_port,
                        client_id,
                    )
                    break
                except Exception as e:
                    if "already in use" in str(e).lower() and attempt < max_attempts - 1:
                        # Try next clientId if current one is in use
                        client_id += 1
                        attempt += 1
                        logger.debug("ClientId %s in use, trying %s", client_id - 1, client_id)
                        self._ib = IB()  # Reset IB connection for retry
                    else:
                        raise
        except ImportError:
            logger.warning("ib_insync not installed: pip install ib_insync")
            self._ib = None
        except Exception as exc:
            logger.error("IBKR connection failed: %s", exc)
            self._ib = None

    def disconnect(self) -> None:
        """Cleanly disconnect from IBKR and release event loop resources."""
        if self._ib:
            try:
                if hasattr(self._ib, "disconnect"):
                    self._ib.disconnect()
                    logger.info("Disconnected from IBKR")
            except Exception as exc:
                logger.error("IBKR disconnect failed: %s", exc)
            finally:
                self._ib = None

    def _connected(self) -> bool:
        return bool(self._ib and self._ib.isConnected())

    def _get_trade_filled_qty(self, trade: Any) -> float:
        """Return filled quantity from an ib_insync Trade object.

        Handles both attribute and callable variants of ``trade.filled``.
        """
        filled_attr = getattr(trade, "filled", 0)
        try:
            value = filled_attr() if callable(filled_attr) else filled_attr
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _cache_contract_currency(self, symbol: str, currency: str) -> None:
        clean_symbol = str(symbol or "").strip().upper()
        clean_currency = str(currency or "").strip().upper()
        if not clean_symbol or not clean_currency:
            return
        self._symbol_currency_cache[clean_symbol] = clean_currency

    def __del__(self) -> None:
        """Ensure cleanup on garbage collection."""
        try:
            self.disconnect()
        except Exception:
            pass

    def get_account_ids(self) -> list[str]:
        if not self._connected():
            return []
        try:
            accounts = self._ib.managedAccounts()
            if isinstance(accounts, (list, tuple)):
                return [str(a) for a in accounts if a]
            if isinstance(accounts, str):
                return [a.strip() for a in accounts.split(",") if a.strip()]
        except Exception as exc:
            logger.error("IBKR managedAccounts read failed: %s", exc)
        return []

    def get_primary_account(self) -> str:
        accounts = self.get_account_ids()
        return accounts[0] if accounts else ""

    def is_paper_account(self) -> bool:
        account = self.get_primary_account().upper()
        return account.startswith("DU")

    def is_live_account(self) -> bool:
        account = self.get_primary_account().upper()
        return account.startswith("U") and not account.startswith("DU")

    def _map_status(self, ib_status: Optional[str]) -> OrderStatus:
        status = (ib_status or "").lower()
        if status in {"filled"}:
            return OrderStatus.FILLED
        if status in {"cancelled", "inactive"}:
            return OrderStatus.CANCELLED
        if status in {"api cancelled", "rejected"}:
            return OrderStatus.REJECTED
        return OrderStatus.PENDING

    def _contract_spec(self, symbol: str) -> dict:
        inferred: dict[str, str]
        if symbol.upper().endswith(".L"):
            inferred = {
                "ib_symbol": symbol[:-2],
                "exchange": "SMART",
                "currency": "GBP",
                "primary_exchange": "LSE",
            }
        else:
            inferred = {
                "ib_symbol": symbol,
                "exchange": "SMART",
                "currency": "USD",
                "primary_exchange": "",
            }

        overrides = self.cfg.ibkr_symbol_overrides or {}
        if symbol in overrides:
            override = overrides[symbol] or {}
            ib_symbol = str(
                override.get("ib_symbol") or override.get("ibSymbol") or inferred["ib_symbol"]
            )
            exchange = str(override.get("exchange") or inferred["exchange"]).upper()
            currency = str(override.get("currency") or inferred["currency"]).upper()
            primary_exchange = str(
                override.get("primary_exchange")
                or override.get("primaryExchange")
                or inferred["primary_exchange"]
            ).upper()
            return {
                "ib_symbol": ib_symbol,
                "exchange": exchange,
                "currency": currency,
                "primary_exchange": primary_exchange,
            }

        return inferred

    def _build_stock_contract(self, symbol: str):
        spec = self._contract_spec(symbol)
        kwargs = {}
        if spec["primary_exchange"]:
            kwargs["primaryExchange"] = spec["primary_exchange"]
        return self._Stock(
            spec["ib_symbol"],
            spec["exchange"],
            spec["currency"],
            **kwargs,
        )

    def get_symbol_currency(self, symbol: str) -> str:
        cache_key = str(symbol or "").strip().upper()
        if cache_key in self._symbol_currency_cache:
            return self._symbol_currency_cache[cache_key]
        return self._contract_spec(symbol)["currency"]

    def get_account_base_currency(self) -> str:
        if not self._connected():
            return ""
        try:
            summary = self._ib.accountSummary()
            for row in summary:
                if getattr(row, "tag", "") == "BaseCurrency":
                    return str(getattr(row, "value", "") or "")
        except Exception as exc:
            logger.error("IBKR base currency read failed: %s", exc)
        return ""

    def submit_order(self, order: Order) -> Order:
        if not self._connected():
            order.status = OrderStatus.REJECTED
            return order

        try:
            qty = max(int(round(order.qty)), 1)
            action = "BUY" if order.side == OrderSide.BUY else "SELL"
            contract = self._build_stock_contract(order.symbol)
            ib_order = self._MarketOrder(action, qty)

            trade = self._ib.placeOrder(contract, ib_order)
            # Wait briefly for order acknowledgment from broker
            self._ib.waitOnUpdate(timeout=3)

            order.order_id = str(getattr(trade.order, "orderId", ""))
            order.status = self._map_status(getattr(trade.orderStatus, "status", None))

            # Poll for fill up to 30 seconds (LSE market orders can take >15s)
            # Key fix: Use waitOnUpdate() in loop instead of sleep() to allow wrapper callbacks
            # Check trade.isDone() or orderStatus.status rather than avgFillPrice
            fill_detected = False
            for poll_attempt in range(30):
                # waitOnUpdate() allows ib_insync wrapper to process broker callbacks
                self._ib.waitOnUpdate(timeout=1)

                # Check if order is filled by examining orderStatus
                status = getattr(trade.orderStatus, "status", None)
                if status == "Filled":
                    avg_fill = float(getattr(trade.orderStatus, "avgFillPrice", 0.0) or 0.0)
                    order.filled_price = avg_fill
                    order.filled_at = datetime.now(timezone.utc)
                    order.status = OrderStatus.FILLED
                    logger.info(
                        "Order %s (%s) filled at %.4f after %d seconds (status: %s)",
                        order.symbol,
                        order.order_id,
                        avg_fill,
                        poll_attempt,
                        status,
                    )
                    fill_detected = True
                    break

                # Fallback: check if Trade object has fills (via Trade.filled property)
                filled_qty = self._get_trade_filled_qty(trade)
                if filled_qty > 0:
                    avg_fill = float(getattr(trade.orderStatus, "avgFillPrice", 0.0) or 0.0)
                    order.filled_price = avg_fill
                    order.filled_at = datetime.now(timezone.utc)
                    order.status = OrderStatus.FILLED
                    logger.info(
                        "Order %s (%s) filled %.0f shares at %.4f after %d seconds (via Trade.filled)",
                        order.symbol,
                        order.order_id,
                        filled_qty,
                        avg_fill,
                        poll_attempt,
                    )
                    fill_detected = True
                    break

            if not fill_detected:
                # After timeout, do final check on status
                status = getattr(trade.orderStatus, "status", None)
                logger.warning(
                    "Order %s (%s) not filled after 30 seconds, final status: %s, "
                    "Trade.filled: %.0f, Trade.isDone: %s",
                    order.symbol,
                    order.order_id,
                    status,
                    self._get_trade_filled_qty(trade),
                    trade.isDone() if hasattr(trade, "isDone") else None,
                )
        except Exception as exc:
            logger.error("IBKR submit_order failed: %s", exc)
            order.status = OrderStatus.REJECTED

        return order

    def cancel_order(self, order_id: str) -> bool:
        if not self._connected():
            return False

        try:
            for trade in self._ib.openTrades():
                if str(getattr(trade.order, "orderId", "")) == str(order_id):
                    self._ib.cancelOrder(trade.order)
                    return True
            return False
        except Exception as exc:
            logger.error("IBKR cancel_order failed: %s", exc)
            return False

    def get_positions(self) -> Dict[str, Position]:
        if not self._connected():
            return {}

        try:
            positions: Dict[str, Position] = {}
            for pos in self._ib.positions():
                symbol = pos.contract.symbol
                qty = float(pos.position)
                avg_entry_price = float(pos.avgCost)
                contract_currency = getattr(pos.contract, "currency", "")
                self._cache_contract_currency(symbol, contract_currency)
                market_price = self._market_price_for_contract(pos.contract) or avg_entry_price
                positions[symbol] = Position(
                    symbol=symbol,
                    qty=qty,
                    avg_entry_price=avg_entry_price,
                    current_price=market_price,
                )
            return positions
        except Exception as exc:
            logger.error("IBKR get_positions failed: %s", exc)
            return {}

    def _market_price(self, symbol: str) -> Optional[float]:
        if not self._connected():
            return None
        try:
            contract = self._build_stock_contract(symbol)
            return self._market_price_for_contract(contract)
        except Exception:
            return None

    def _market_price_for_contract(self, contract) -> Optional[float]:
        if not self._connected():
            return None
        try:
            ticker = self._ib.reqMktData(contract, "", False, False)
            self._ib.sleep(0.2)
            market_price = ticker.marketPrice()
            return float(market_price) if market_price else None
        except Exception:
            return None

    def _account_value(self, tag: str) -> float:
        if not self._connected():
            return 0.0
        try:
            summary = self._ib.accountSummary()
            for row in summary:
                if row.tag == tag:
                    return float(row.value)
        except Exception as exc:
            logger.error("IBKR account summary read failed: %s", exc)
        return 0.0

    def get_portfolio_value(self) -> float:
        return self._account_value("NetLiquidation")

    def get_cash(self) -> float:
        return self._account_value("TotalCashValue")
