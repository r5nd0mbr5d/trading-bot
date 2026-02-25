"""Unit tests for provider-specific symbol normalization."""

import pytest

from src.data.symbol_utils import normalize_symbol


@pytest.mark.parametrize(
    "source_symbol,expected",
    [
        ("BTCGBP", "BTC-GBP"),
        ("BTC/GBP", "BTC-GBP"),
        ("HSBA.L", "HSBA.L"),
    ],
)
def test_normalize_symbol_for_yfinance(source_symbol: str, expected: str):
    assert normalize_symbol(source_symbol, "yfinance") == expected


@pytest.mark.parametrize(
    "source_symbol,expected",
    [
        ("BTC-GBP", "BTCGBP"),
        ("BTC/GBP", "BTCGBP"),
        ("BTCGBP", "BTCGBP"),
    ],
)
def test_normalize_symbol_for_binance(source_symbol: str, expected: str):
    assert normalize_symbol(source_symbol, "binance") == expected


@pytest.mark.parametrize(
    "source_symbol,expected",
    [
        ("BTCGBP", "BTC-GBP"),
        ("BTC/GBP", "BTC-GBP"),
        ("BTC-GBP", "BTC-GBP"),
    ],
)
def test_normalize_symbol_for_coinbase(source_symbol: str, expected: str):
    assert normalize_symbol(source_symbol, "coinbase") == expected


@pytest.mark.parametrize(
    "source_symbol,expected",
    [
        ("BTC-GBP", "BTC/GBP"),
        ("BTCGBP", "BTC/GBP"),
        ("AAPL", "AAPL"),
    ],
)
def test_normalize_symbol_for_alpaca(source_symbol: str, expected: str):
    assert normalize_symbol(source_symbol, "alpaca") == expected


@pytest.mark.parametrize(
    "source_symbol,expected",
    [
        ("BTCGBP", "BTC"),
        ("BTC-GBP", "BTC"),
        ("BTC/GBP", "BTC"),
        ("HSBA.L", "HSBA"),
    ],
)
def test_normalize_symbol_for_ibkr(source_symbol: str, expected: str):
    assert normalize_symbol(source_symbol, "ibkr") == expected


def test_unknown_provider_raises_value_error():
    with pytest.raises(ValueError):
        normalize_symbol("BTCGBP", "unknown")
