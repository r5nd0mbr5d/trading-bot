"""Unit tests for VaR/CVaR module."""

import numpy as np
import pytest

from src.risk.var import PortfolioVaR, historical_var_cvar


class TestHistoricalVarCvar:

    def test_known_sequence_all_same_loss(self):
        # 100 returns: 5 at -10%, 95 at +1%
        returns = np.array([-0.10] * 5 + [0.01] * 95)
        var, cvar = historical_var_cvar(returns, confidence=0.95)
        # cutoff = max(int(0.05*100), 1) = 5
        # sorted: [-0.10]*5 then [0.01]*95
        # var  = -sorted[4] = 0.10
        # cvar = -mean(sorted[:5]) = 0.10
        assert var == pytest.approx(0.10, abs=1e-6)
        assert cvar == pytest.approx(0.10, abs=1e-6)

    def test_mixed_losses(self):
        # 20 returns: 1 extreme loss, 19 small gains
        returns = np.array([-0.20] + [0.01] * 19)
        var, cvar = historical_var_cvar(returns, confidence=0.95)
        # cutoff = max(int(0.05*20), 1) = max(1, 1) = 1
        # var = -sorted[0] = 0.20
        # cvar = -mean([-0.20]) = 0.20
        assert var == pytest.approx(0.20, abs=1e-6)
        assert cvar == pytest.approx(0.20, abs=1e-6)

    def test_all_positive_returns(self):
        # No losses — VaR and CVaR should be 0
        returns = np.array([0.01] * 100)
        var, cvar = historical_var_cvar(returns)
        assert var == pytest.approx(0.0, abs=1e-6)
        assert cvar == pytest.approx(0.0, abs=1e-6)

    def test_insufficient_data_returns_zeros(self):
        var, cvar = historical_var_cvar(np.array([0.01]))
        assert var == 0.0
        assert cvar == 0.0

    def test_empty_returns_zeros(self):
        var, cvar = historical_var_cvar(np.array([]))
        assert var == 0.0
        assert cvar == 0.0

    def test_var_always_non_negative(self):
        rng = np.random.default_rng(42)
        returns = rng.normal(0.001, 0.02, 500)
        var, cvar = historical_var_cvar(returns)
        assert var >= 0.0
        assert cvar >= 0.0

    def test_cvar_greater_or_equal_var(self):
        rng = np.random.default_rng(0)
        returns = rng.normal(0, 0.015, 300)
        var, cvar = historical_var_cvar(returns)
        assert cvar >= var - 1e-9


class TestPortfolioVaR:

    def test_insufficient_history_returns_zero(self):
        pvar = PortfolioVaR(window=252)
        pvar.update(-0.02)
        pvar.update(0.01)
        assert pvar.var95 == 0.0
        assert pvar.cvar95 == 0.0

    def test_within_limit_when_no_history(self):
        pvar = PortfolioVaR()
        assert pvar.is_within_limit(0.05) is True

    def test_within_limit_disabled_when_zero(self):
        pvar = PortfolioVaR()
        for _ in range(100):
            pvar.update(-0.10)
        assert pvar.is_within_limit(0.0) is True  # gate disabled

    def test_history_length_tracks_updates(self):
        pvar = PortfolioVaR(window=10)
        for i in range(7):
            pvar.update(0.01 * i)
        assert pvar.history_length == 7

    def test_rolling_window_caps_history(self):
        pvar = PortfolioVaR(window=10)
        for _ in range(20):
            pvar.update(0.01)
        assert pvar.history_length == 10

    def test_blocks_when_var_exceeds_limit(self):
        pvar = PortfolioVaR(window=252)
        # Feed 50 returns of -20% — extreme losses
        for _ in range(50):
            pvar.update(-0.20)
        # var95 >> 0.05 → should be blocked
        assert pvar.is_within_limit(0.05) is False

    def test_allows_when_var_within_limit(self):
        pvar = PortfolioVaR(window=252)
        # Feed 50 tiny returns — virtually no VaR
        for _ in range(50):
            pvar.update(0.001)
        assert pvar.is_within_limit(0.05) is True

    def test_update_feeds_computation(self):
        pvar = PortfolioVaR(window=252)
        for _ in range(50):
            pvar.update(-0.05)
        assert pvar.var95 > 0.0
        assert pvar.cvar95 > 0.0
