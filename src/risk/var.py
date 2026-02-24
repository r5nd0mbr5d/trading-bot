"""Portfolio VaR and CVaR — Historical Simulation.

Computes 1-day 95% Value at Risk (VaR) and Conditional VaR (CVaR / Expected
Shortfall) using the historical simulation method over a rolling window of
daily portfolio returns.

Design decisions (Q8 research answer):
  - Historical simulation: no distributional assumptions, captures fat tails.
  - 252-day rolling window (≈ 1 trading year).
  - VaR95 used as a hard gate in RiskManager.approve_signal().
  - CVaR95 exposed as a monitoring metric only.

Usage:
    from src.risk.var import PortfolioVaR

    pvar = PortfolioVaR(window=252)
    pvar.update(-0.012)   # feed daily return after each bar closes
    print(pvar.var95)     # e.g. 0.023 → VaR = 2.3% of portfolio

    # In RiskManager:
    if not pvar.is_within_limit(max_var_pct=0.05):
        return None  # reject order
"""

import logging
from collections import deque
from typing import Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Minimum observations before VaR is considered meaningful.
# Below this threshold we return 0.0 (→ within any limit → no blocking).
_MIN_HISTORY = 10


def historical_var_cvar(
    returns: np.ndarray,
    confidence: float = 0.95,
) -> Tuple[float, float]:
    """
    Historical simulation VaR and CVaR.

    Args:
        returns:    1-D numpy array of daily portfolio returns.
                    Negative values are losses (e.g., -0.02 = -2%).
        confidence: Confidence level (default 0.95 → 95%).

    Returns:
        (var, cvar) as positive floats representing loss magnitude.
        E.g., (0.02, 0.03) → VaR = 2%, CVaR = 3%.

    Formula:
        Sorts returns ascending (worst losses first), then:
          cutoff = max(floor((1 - confidence) × N), 1)
          VaR    = -sorted_returns[cutoff - 1]   (loss at the boundary)
          CVaR   = -mean(sorted_returns[:cutoff]) (average of tail losses)
    """
    if len(returns) < 2:
        return 0.0, 0.0

    sorted_returns = np.sort(returns)
    n = len(sorted_returns)
    cutoff = max(int((1 - confidence) * n), 1)

    var = float(-sorted_returns[cutoff - 1])
    cvar = float(-sorted_returns[:cutoff].mean())

    return max(var, 0.0), max(cvar, 0.0)


class PortfolioVaR:
    """
    Rolling historical VaR/CVaR tracker.

    Feed daily portfolio returns via update() after each bar closes.
    Read var95 / cvar95 properties for current risk metrics.
    Use is_within_limit() in RiskManager to gate new orders.
    """

    def __init__(self, window: int = 252, confidence: float = 0.95):
        """
        Args:
            window:     Rolling window size in trading days (default 252 = 1 year).
            confidence: VaR/CVaR confidence level (default 0.95).
        """
        self._window = window
        self._confidence = confidence
        self._returns: deque = deque(maxlen=window)

    def update(self, daily_return: float) -> None:
        """
        Append a daily portfolio return observation.

        Args:
            daily_return: Fractional return for the day (e.g., -0.012 for -1.2%).
        """
        self._returns.append(daily_return)

    @property
    def var95(self) -> float:
        """
        One-day VaR at the configured confidence level.
        Returns 0.0 when insufficient history (< _MIN_HISTORY observations).
        Positive value = loss magnitude (e.g., 0.02 → 2%).
        """
        if len(self._returns) < _MIN_HISTORY:
            return 0.0
        var, _ = historical_var_cvar(np.array(self._returns), self._confidence)
        return var

    @property
    def cvar95(self) -> float:
        """
        CVaR (Expected Shortfall) at the configured confidence level.
        Returns 0.0 when insufficient history.
        Positive value = average tail loss magnitude.
        """
        if len(self._returns) < _MIN_HISTORY:
            return 0.0
        _, cvar = historical_var_cvar(np.array(self._returns), self._confidence)
        return cvar

    def is_within_limit(self, max_var_pct: float) -> bool:
        """
        Return True if the portfolio is safe to trade (VaR within limit).

        Returns True when:
          - max_var_pct <= 0 (VaR gate disabled)
          - Insufficient history (< _MIN_HISTORY days)
          - Current VaR95 <= max_var_pct

        Returns False (block trading) only when we have enough history
        AND the VaR exceeds the configured limit.

        Args:
            max_var_pct: Maximum allowed 1-day VaR as a fraction (e.g., 0.05 = 5%).
        """
        if max_var_pct <= 0:
            return True  # Gate disabled
        if len(self._returns) < _MIN_HISTORY:
            return True  # Insufficient history — don't block at startup
        return self.var95 <= max_var_pct

    @property
    def history_length(self) -> int:
        """Number of daily return observations currently held."""
        return len(self._returns)
