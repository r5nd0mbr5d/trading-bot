"""Unit tests for CoinbaseBroker adapter (mocked client only)."""

from config.settings import Settings
from src.data.models import Order, OrderSide, OrderStatus
from src.execution.broker import CoinbaseBroker


class _FakeCoinbaseClient:
    def __init__(self):
        self.last_buy = None
        self.last_sell = None
        self.last_cancel = None

    def market_order_buy(self, **kwargs):
        self.last_buy = kwargs
        return {"order_id": "cb_buy_1", "status": "FILLED", "filled_price": "50000"}

    def market_order_sell(self, **kwargs):
        self.last_sell = kwargs
        return {"order_id": "cb_sell_1", "status": "FILLED", "filled_price": "51000"}

    def cancel_orders(self, **kwargs):
        self.last_cancel = kwargs
        return {"results": [{"success": True}]}

    def get_accounts(self):
        return {
            "accounts": [
                {
                    "currency": "BTC",
                    "available_balance": {"value": "0.010"},
                    "hold": {"value": "0.005"},
                },
                {
                    "currency": "GBP",
                    "available_balance": {"value": "250.0"},
                    "hold": {"value": "10.0"},
                },
            ]
        }

    def get_product(self, **kwargs):
        product_id = kwargs.get("product_id")
        prices = {"BTC-GBP": "50000"}
        return {"price": prices.get(product_id, "0")}


def _make_broker(monkeypatch):
    monkeypatch.setattr(CoinbaseBroker, "_connect", lambda self: None)
    broker = CoinbaseBroker(Settings())
    broker._client = _FakeCoinbaseClient()
    return broker


def test_submit_buy_order_uses_coinbase_symbol(monkeypatch):
    broker = _make_broker(monkeypatch)
    order = Order(symbol="BTCGBP", side=OrderSide.BUY, qty=0.002)

    result = broker.submit_order(order)

    assert result.status == OrderStatus.FILLED
    assert result.order_id == "cb_buy_1"
    assert broker._client.last_buy["product_id"] == "BTC-GBP"


def test_submit_sell_order_uses_coinbase_symbol(monkeypatch):
    broker = _make_broker(monkeypatch)
    order = Order(symbol="BTC/GBP", side=OrderSide.SELL, qty=0.002)

    result = broker.submit_order(order)

    assert result.status == OrderStatus.FILLED
    assert result.order_id == "cb_sell_1"
    assert broker._client.last_sell["product_id"] == "BTC-GBP"


def test_cancel_order_calls_cancel_orders(monkeypatch):
    broker = _make_broker(monkeypatch)

    cancelled = broker.cancel_order("cb_buy_1")

    assert cancelled is True
    assert broker._client.last_cancel == {"order_ids": ["cb_buy_1"]}


def test_get_positions_parses_accounts(monkeypatch):
    broker = _make_broker(monkeypatch)

    positions = broker.get_positions()

    assert "BTC-GBP" in positions
    assert positions["BTC-GBP"].qty == 0.015


def test_get_cash_returns_free_gbp(monkeypatch):
    broker = _make_broker(monkeypatch)

    cash = broker.get_cash()

    assert cash == 250.0
