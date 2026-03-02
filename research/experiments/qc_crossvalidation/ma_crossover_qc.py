"""QuantConnect port of MA Crossover strategy for cross-validation.

This algorithm replicates the trading-bot's MACrossoverStrategy
(src/strategies/ma_crossover.py) using QuantConnect's QCAlgorithm
interface and built-in indicators.

Purpose:
    Independent validation of the project's backtest results against
    QuantConnect's LEAN engine, which uses a different slippage model,
    fill assumptions, and data source.

Usage:
    1. Copy this file into a new QuantConnect algorithm on quantconnect.com
    2. Click Backtest  (free tier, 1 node, minute-bar equity data)
    3. Compare Sharpe, max-drawdown, and trade count against Step 1 results

Date range:  2025-01-01  to  2026-01-01  (matches Step 1 sign-off window)
Symbols:     HSBA.L, LLOY.L, BP.L, RIO.L, GLEN.L  (UK LSE basket)

Parameters (matching config/settings.py defaults):
    fast_period = 20
    slow_period = 50

Notes:
    - QuantConnect uses SimpleMovingAverage (SMA) by default; our bot also
      uses a simple rolling mean, so the indicator semantics are identical.
    - QuantConnect applies a default slippage model (equity: 0 for limit,
      half-spread for market) and an Interactive-Brokers-style commission
      model.  Our PaperBroker backtest uses zero slippage / zero commission.
      Any Sharpe or drawdown divergence likely stems from this difference.
    - LEAN resolves LSE symbols with the ".L" suffix via its market mapping.
"""

# ── QuantConnect boilerplate ────────────────────────────────────────────
# When running on QuantConnect Cloud, the `from AlgorithmImports import *`
# line auto-imports QCAlgorithm, Resolution, Market, OrderDirection, etc.
# For local linting / IDE support this import will fail — that is expected.
try:
    from AlgorithmImports import *  # noqa: F401, F403
except ImportError:
    # Running outside QuantConnect (local lint / reference only)
    pass


class MACrossoverQC:
    """QCAlgorithm implementation of the MA Crossover strategy.

    Mirrors src/strategies/ma_crossover.py:
        BUY  — fast SMA crosses above slow SMA  (golden cross)
        SELL — fast SMA crosses below slow SMA   (death cross)

    Attributes
    ----------
    FAST_PERIOD : int
        Rolling window length for the fast moving average (default 20).
    SLOW_PERIOD : int
        Rolling window length for the slow moving average (default 50).
    SYMBOLS : list[str]
        Ticker basket matching Step 1 sign-off.
    """

    # ── Parameters (match config/settings.py) ───────────────────────────
    FAST_PERIOD: int = 20
    SLOW_PERIOD: int = 50
    SYMBOLS = ["HSBA.L", "LLOY.L", "BP.L", "RIO.L", "GLEN.L"]

    # ── Lifecycle ────────────────────────────────────────────────────────

    def Initialize(self) -> None:  # noqa: N802  (QuantConnect naming)
        """Set up algorithm parameters, universe, and indicators."""
        self.SetStartDate(2025, 1, 1)
        self.SetEndDate(2026, 1, 1)
        self.SetCash(100_000)

        self._fast = {}
        self._slow = {}
        self._prev_above = {}

        for ticker in self.SYMBOLS:
            equity = self.AddEquity(ticker, Resolution.Daily, Market.UK)
            sym = equity.Symbol
            self._fast[sym] = self.SMA(sym, self.FAST_PERIOD, Resolution.Daily)
            self._slow[sym] = self.SMA(sym, self.SLOW_PERIOD, Resolution.Daily)
            self._prev_above[sym] = None

        # Warm up indicators so we don't get premature signals
        self.SetWarmUp(self.SLOW_PERIOD + 1)

    def OnData(self, data) -> None:  # noqa: N802
        """Process daily bars — detect crossover and submit orders."""
        if self.IsWarmingUp:
            return

        for sym in list(self._fast.keys()):
            if not data.ContainsKey(sym) or data[sym] is None:
                continue

            fast_val = self._fast[sym].Current.Value
            slow_val = self._slow[sym].Current.Value

            if not self._fast[sym].IsReady or not self._slow[sym].IsReady:
                continue

            curr_above = fast_val > slow_val

            if self._prev_above[sym] is not None:
                if curr_above and not self._prev_above[sym]:
                    # Golden cross — go long
                    spread = (fast_val - slow_val) / slow_val
                    strength = min(abs(spread) * 10, 1.0)
                    qty = self._position_size(sym, data[sym].Close, strength)
                    if qty > 0:
                        self.MarketOrder(sym, qty)
                        self.Debug(
                            f"BUY  {sym} qty={qty} "
                            f"fast={fast_val:.4f} slow={slow_val:.4f}"
                        )

                elif not curr_above and self._prev_above[sym]:
                    # Death cross — close position
                    if self.Portfolio[sym].Invested:
                        self.Liquidate(sym)
                        self.Debug(
                            f"SELL {sym} "
                            f"fast={fast_val:.4f} slow={slow_val:.4f}"
                        )

            self._prev_above[sym] = curr_above

    # ── Helpers ──────────────────────────────────────────────────────────

    def _position_size(self, symbol, price: float, strength: float) -> int:
        """Compute order quantity matching RiskManager logic.

        Uses a fixed 2 % risk-per-trade allocation scaled by signal strength,
        consistent with the project's default RiskConfig.max_position_pct.

        Parameters
        ----------
        symbol : Symbol
            QuantConnect Symbol object.
        price : float
            Current close price for the equity.
        strength : float
            Signal strength in [0.0, 1.0], used to scale position size.

        Returns
        -------
        int
            Number of shares to buy (floored to whole shares).
        """
        if price <= 0:
            return 0
        equity = self.Portfolio.TotalPortfolioValue
        allocation = equity * 0.02 * strength  # 2% risk * strength
        return int(allocation / price)
