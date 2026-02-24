"""Unit tests for CLI runtime profiles."""

from config.settings import Settings
from main import apply_runtime_profile


def test_apply_runtime_profile_uk_paper_sets_ibkr_defaults():
    settings = Settings()

    apply_runtime_profile(settings, "uk_paper")

    assert settings.broker.provider == "ibkr"
    assert settings.broker.paper_trading is True
    assert settings.broker.ibkr_port == 7497
    assert settings.base_currency == "GBP"
    assert settings.fx_rates["USD_GBP"] == 0.79
    assert settings.market_timezone == "Europe/London"
    assert settings.paper_guardrails.session_timezone == "Europe/London"
    assert settings.data.symbols == ["HSBA.L", "VOD.L", "BP.L", "BARC.L", "SHEL.L"]
    assert settings.broker.ibkr_symbol_overrides["HSBA.L"]["ib_symbol"] == "HSBA"
    assert settings.broker.ibkr_symbol_overrides["HSBA.L"]["currency"] == "GBP"


def test_apply_runtime_profile_default_no_changes():
    settings = Settings()
    original_provider = settings.broker.provider
    original_symbols = list(settings.data.symbols)

    apply_runtime_profile(settings, "default")

    assert settings.broker.provider == original_provider
    assert settings.data.symbols == original_symbols
