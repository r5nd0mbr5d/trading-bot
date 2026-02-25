"""Unit tests for BinanceBroker adapter (mocked client only)."""

import sys
from types import SimpleNamespace

from config.settings import Settings
from src.data.models import Order, OrderSide, OrderStatus
from src.execution.broker import BinanceBroker


class _FakeBinanceClient:
    def __init__(self, *_args, **kwargs):
        self.testnet = kwargs.get("testnet", False)
        self.API_URL = "https://api.binance.com/api"
        self.last_buy = None
        self.last_sell = None
        self.last_cancel = None

    def get_symbol_info(self, symbol):
        _ = symbol
        return {
            "filters": [
                {
                    "filterType": "LOT_SIZE",
                    "stepSize": "0.001",
                    "minQty": "0.001",
                }
            ]
        }

    def order_market_buy(self, **kwargs):
        self.last_buy = kwargs
        return {
            "orderId": 1001,
            "status": "FILLED",
            "fills": [{"price": "50000", "qty": str(kwargs.get("quantity", 0.0))}],
        }

    def order_market_sell(self, **kwargs):
        self.last_sell = kwargs
        return {
            "orderId": 1002,
            "status": "FILLED",
            "fills": [{"price": "51000", "qty": str(kwargs.get("quantity", 0.0))}],
        }

    def cancel_order(self, **kwargs):
        self.last_cancel = kwargs
        return {"status": "CANCELED"}

    def get_account(self):
        return {
            "balances": [
                {"asset": "BTC", "free": "0.010", "locked": "0.005"},
                {"asset": "ETH", "free": "0.000", "locked": "0.000"},
                {"asset": "GBP", "free": "250.0", "locked": "10.0"},
            ]
        }

    def get_symbol_ticker(self, **kwargs):
        symbol = kwargs.get("symbol")
        prices = {"BTCGBP": "50000"}
        return {"price": prices.get(symbol, "0")}


def _make_broker(monkeypatch):
    monkeypatch.setattr(BinanceBroker, "_connect", lambda self: None)
    broker = BinanceBroker(Settings())
    broker._client = _FakeBinanceClient()
    return broker


def test_connect_uses_testnet_base_url(monkeypatch):
    fake_module = SimpleNamespace(Client=_FakeBinanceClient)
    monkeypatch.setitem(sys.modules, "binance.client", fake_module)

    settings = Settings()
    settings.broker.binance_testnet = True
    broker = BinanceBroker(settings)

    assert broker._client is not None
    assert broker._client.API_URL == "https://testnet.binance.vision/api"


def test_submit_buy_order_normalizes_symbol_and_rounds_quantity(monkeypatch):
    broker = _make_broker(monkeypatch)
    order = Order(symbol="BTC-GBP", side=OrderSide.BUY, qty=0.0019)

    result = broker.submit_order(order)

    assert result.status == OrderStatus.FILLED
    assert result.order_id == "1001"
    assert broker._client.last_buy["symbol"] == "BTCGBP"
    assert broker._client.last_buy["quantity"] == 0.001


def test_submit_sell_order_calls_market_sell(monkeypatch):
    broker = _make_broker(monkeypatch)
    order = Order(symbol="BTC/GBP", side=OrderSide.SELL, qty=0.0022)

    result = broker.submit_order(order)

    assert result.status == OrderStatus.FILLED
    assert result.order_id == "1002"
    assert broker._client.last_sell["symbol"] == "BTCGBP"


def test_cancel_order_uses_symbol_from_order_cache(monkeypatch):
    broker = _make_broker(monkeypatch)
    order = Order(symbol="BTCGBP", side=OrderSide.BUY, qty=0.002)
    submitted = broker.submit_order(order)

    cancelled = broker.cancel_order(submitted.order_id)

    assert cancelled is True
    assert broker._client.last_cancel == {"symbol": "BTCGBP", "orderId": 1001}


def test_get_positions_parses_balances(monkeypatch):
    broker = _make_broker(monkeypatch)

    positions = broker.get_positions()

    assert "BTCGBP" in positions
    assert positions["BTCGBP"].qty == 0.015


def test_get_cash_returns_free_gbp(monkeypatch):
    broker = _make_broker(monkeypatch)

    cash = broker.get_cash()

    assert cash == 250.0
