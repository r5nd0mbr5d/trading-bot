"""Unit tests for IBKR broker adapter."""

import sys
from types import SimpleNamespace

from config.settings import Settings
from src.data.models import Order, OrderSide, OrderStatus
from src.execution.ibkr_broker import IBKRBroker


def _make_broker(monkeypatch):
    monkeypatch.setattr(IBKRBroker, "_connect", lambda self: None)
    broker = IBKRBroker(Settings())
    broker._ib = None
    return broker


def test_map_status_variants(monkeypatch):
    broker = _make_broker(monkeypatch)
    assert broker._map_status("Filled") == OrderStatus.FILLED
    assert broker._map_status("cancelled") == OrderStatus.CANCELLED
    assert broker._map_status("api cancelled") == OrderStatus.REJECTED
    assert broker._map_status("unknown") == OrderStatus.PENDING


def test_submit_order_rejected_when_disconnected(monkeypatch):
    broker = _make_broker(monkeypatch)
    order = Order(symbol="AAPL", side=OrderSide.BUY, qty=1)

    result = broker.submit_order(order)

    assert result.status == OrderStatus.REJECTED


def test_get_account_ids_parses_managed_accounts(monkeypatch):
    broker = _make_broker(monkeypatch)

    class FakeIB:
        def isConnected(self):
            return True

        def managedAccounts(self):
            return "DU12345,U12345"

    broker._ib = FakeIB()

    assert broker.get_account_ids() == ["DU12345", "U12345"]
    assert broker.get_primary_account() == "DU12345"
    assert broker.is_paper_account() is True
    assert broker.is_live_account() is False


def test_get_positions_parses_ibkr_position_rows(monkeypatch):
    broker = _make_broker(monkeypatch)

    class FakeIB:
        def isConnected(self):
            return True

        def positions(self):
            return [
                SimpleNamespace(
                    contract=SimpleNamespace(symbol="VOD"),
                    position=5,
                    avgCost=120.5,
                )
            ]

    broker._ib = FakeIB()
    monkeypatch.setattr(broker, "_market_price", lambda symbol: 121.0)

    positions = broker.get_positions()

    assert "VOD" in positions
    assert positions["VOD"].qty == 5.0
    assert positions["VOD"].avg_entry_price == 120.5
    assert positions["VOD"].current_price == 121.0


def test_build_stock_contract_infers_lse_for_dot_l_symbol(monkeypatch):
    broker = _make_broker(monkeypatch)
    captured = {}

    def fake_stock(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return SimpleNamespace()

    broker._Stock = fake_stock

    broker._build_stock_contract("HSBA.L")

    assert captured["args"] == ("HSBA", "SMART", "GBP")
    assert captured["kwargs"] == {"primaryExchange": "LSE"}


def test_build_stock_contract_uses_symbol_override(monkeypatch):
    settings = Settings()
    settings.broker.ibkr_symbol_overrides = {
        "VOD.L": {
            "ib_symbol": "VOD",
            "exchange": "LSE",
            "currency": "GBP",
            "primary_exchange": "LSE",
        }
    }
    monkeypatch.setattr(IBKRBroker, "_connect", lambda self: None)
    broker = IBKRBroker(settings)
    broker._ib = None

    captured = {}

    def fake_stock(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return SimpleNamespace()

    broker._Stock = fake_stock

    broker._build_stock_contract("VOD.L")

    assert captured["args"] == ("VOD", "LSE", "GBP")
    assert captured["kwargs"] == {"primaryExchange": "LSE"}


def test_contract_spec_partial_override_preserves_uk_defaults(monkeypatch):
    settings = Settings()
    settings.broker.ibkr_symbol_overrides = {
        "HSBA.L": {
            "exchange": "LSE",
        }
    }
    monkeypatch.setattr(IBKRBroker, "_connect", lambda self: None)
    broker = IBKRBroker(settings)
    broker._ib = None

    spec = broker._contract_spec("HSBA.L")

    assert spec["ib_symbol"] == "HSBA"
    assert spec["exchange"] == "LSE"
    assert spec["currency"] == "GBP"
    assert spec["primary_exchange"] == "LSE"


def test_contract_spec_accepts_camel_case_override_keys(monkeypatch):
    settings = Settings()
    settings.broker.ibkr_symbol_overrides = {
        "VOD.L": {
            "ibSymbol": "VOD",
            "exchange": "smart",
            "currency": "gbp",
            "primaryExchange": "lse",
        }
    }
    monkeypatch.setattr(IBKRBroker, "_connect", lambda self: None)
    broker = IBKRBroker(settings)
    broker._ib = None

    spec = broker._contract_spec("VOD.L")

    assert spec == {
        "ib_symbol": "VOD",
        "exchange": "SMART",
        "currency": "GBP",
        "primary_exchange": "LSE",
    }


def test_get_symbol_currency_from_contract_spec(monkeypatch):
    broker = _make_broker(monkeypatch)
    assert broker.get_symbol_currency("AAPL") == "USD"
    assert broker.get_symbol_currency("HSBA.L") == "GBP"


def test_get_account_base_currency(monkeypatch):
    broker = _make_broker(monkeypatch)

    class FakeIB:
        def isConnected(self):
            return True

        def accountSummary(self):
            return [
                SimpleNamespace(tag="NetLiquidation", value="100000"),
                SimpleNamespace(tag="BaseCurrency", value="GBP"),
            ]

    broker._ib = FakeIB()
    assert broker.get_account_base_currency() == "GBP"


def test_connect_retries_with_incremented_client_id(monkeypatch):
    calls = []

    class FakeIB:
        def connect(self, host, port, clientId, timeout):
            calls.append(clientId)
            if len(calls) == 1:
                raise RuntimeError("client id is already in use")

        def isConnected(self):
            return True

    fake_module = SimpleNamespace(
        IB=lambda: FakeIB(),
        MarketOrder=lambda *args, **kwargs: SimpleNamespace(),
        Stock=lambda *args, **kwargs: SimpleNamespace(),
        util=SimpleNamespace(patchAsyncio=lambda: None),
    )
    monkeypatch.setitem(sys.modules, "ib_insync", fake_module)

    settings = Settings()
    settings.broker.ibkr_client_id = 7
    broker = IBKRBroker(settings)

    assert calls == [7, 8]
    assert broker._connected() is True


def test_submit_order_maps_rejected_status(monkeypatch):
    broker = _make_broker(monkeypatch)

    class FakeIB:
        def isConnected(self):
            return True

        def placeOrder(self, contract, ib_order):
            return SimpleNamespace(
                order=SimpleNamespace(orderId=101),
                orderStatus=SimpleNamespace(status="Rejected", avgFillPrice=0.0),
            )

        def waitOnUpdate(self, timeout):
            return None

    broker._ib = FakeIB()
    broker._Stock = lambda *args, **kwargs: SimpleNamespace()
    broker._MarketOrder = lambda *args, **kwargs: SimpleNamespace()

    order = Order(symbol="AAPL", side=OrderSide.BUY, qty=1)
    result = broker.submit_order(order)

    assert result.order_id == "101"
    assert result.status == OrderStatus.REJECTED
