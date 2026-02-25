"""Provider-specific symbol normalization helpers."""


def normalize_symbol(symbol: str, provider: str) -> str:
    """Normalize symbol format for a target provider.

    Parameters
    ----------
    symbol
        Symbol as entered by runtime/backtest settings.
    provider
        Provider identifier: ``yfinance``, ``binance``, ``alpaca``, ``ibkr``.

    Returns
    -------
    str
        Provider-normalized symbol.

    Raises
    ------
    ValueError
        If symbol/provider is invalid or provider is unsupported.
    """
    clean_symbol = (symbol or "").strip().upper()
    clean_provider = (provider or "").strip().lower()

    if not clean_symbol:
        raise ValueError("symbol is required")
    if not clean_provider:
        raise ValueError("provider is required")

    if clean_provider == "yfinance":
        if clean_symbol in {"BTCGBP", "BTC/GBP"}:
            return "BTC-GBP"
        return clean_symbol

    if clean_provider == "binance":
        if clean_symbol in {"BTC-GBP", "BTC/GBP", "BTCGBP"}:
            return "BTCGBP"
        return clean_symbol

    if clean_provider == "alpaca":
        if clean_symbol in {"BTCGBP", "BTC-GBP", "BTC/GBP"}:
            return "BTC/GBP"
        return clean_symbol

    if clean_provider == "ibkr":
        if clean_symbol in {"BTCGBP", "BTC-GBP", "BTC/GBP"}:
            return "BTC"
        if clean_symbol.endswith(".L"):
            return clean_symbol[:-2]
        return clean_symbol

    raise ValueError(f"Unsupported provider: {provider}")
