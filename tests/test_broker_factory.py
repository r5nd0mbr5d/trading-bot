"""Tests for runtime broker selection and crypto fallback routing."""

from config.settings import Settings
from src.execution.broker import BrokerConnectionError
from src.trading.loop import build_runtime_broker


class _PrimaryUnavailableBroker:
    def __init__(self, _settings):
        raise BrokerConnectionError("primary down")


class _FallbackBroker:
    def __init__(self, _settings):
        self.connected = True


class _PrimaryBroker:
    def __init__(self, _settings):
        self.connected = True


class _IbkrBroker:
    def __init__(self, _settings):
        self.connected = True


class _AlpacaBroker:
    def __init__(self, _settings):
        self.connected = True


def test_build_runtime_broker_falls_back_to_binance_for_crypto(monkeypatch):
    settings = Settings()
    settings.data.symbols = ["BTCGBP"]
    settings.broker.crypto_primary_provider = "coinbase"
    settings.broker.crypto_fallback_provider = "binance"

    monkeypatch.setattr("src.execution.broker.CoinbaseBroker", _PrimaryUnavailableBroker)
    monkeypatch.setattr("src.execution.broker.BinanceBroker", _FallbackBroker)

    broker = build_runtime_broker(settings)

    assert isinstance(broker, _FallbackBroker)


def test_build_runtime_broker_uses_crypto_primary_when_available(monkeypatch):
    settings = Settings()
    settings.data.symbols = ["BTC-GBP"]
    settings.broker.crypto_primary_provider = "coinbase"

    monkeypatch.setattr("src.execution.broker.CoinbaseBroker", _PrimaryBroker)

    broker = build_runtime_broker(settings)

    assert isinstance(broker, _PrimaryBroker)


def test_build_runtime_broker_uses_ibkr_for_equities(monkeypatch):
    settings = Settings()
    settings.data.symbols = ["HSBA.L"]
    settings.broker.provider = "ibkr"

    monkeypatch.setattr("src.execution.ibkr_broker.IBKRBroker", _IbkrBroker)

    broker = build_runtime_broker(settings)

    assert isinstance(broker, _IbkrBroker)


def test_build_runtime_broker_uses_alpaca_for_equities_non_ibkr(monkeypatch):
    settings = Settings()
    settings.data.symbols = ["AAPL"]
    settings.broker.provider = "alpaca"

    monkeypatch.setattr("src.execution.broker.AlpacaBroker", _AlpacaBroker)

    broker = build_runtime_broker(settings)

    assert isinstance(broker, _AlpacaBroker)
