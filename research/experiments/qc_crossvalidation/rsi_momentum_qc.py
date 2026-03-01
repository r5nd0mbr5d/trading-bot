"""QuantConnect port of RSI Momentum strategy for cross-validation.

This algorithm replicates the trading-bot's RSIMomentumStrategy
(src/strategies/rsi_momentum.py) using QuantConnect's QCAlgorithm
interface and built-in RSI indicator.

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
    rsi_period    = 14
    rsi_oversold  = 30
    rsi_overbought = 70

Notes:
    - QuantConnect's built-in RSI uses Wilder's smoothing (exponential
      moving average with span=period), which matches our _compute_rsi()
      implementation (ewm with span=period, adjust=False).
    - LEAN applies IB-style commissions and a half-spread slippage model
      for market orders. Our PaperBroker uses zero costs, so slight
      performance divergence is expected.
    - LEAN's RSI indicator fires after period+1 bars of warm-up data,
      matching our min_bars_required() = period + 2 (we need 2 consecutive
      RSI values for the crossover check).
"""

# ── QuantConnect boilerplate ────────────────────────────────────────────
try:
    from AlgorithmImports import *  # noqa: F401, F403
except ImportError:
    pass


class RSIMomentumQC:
    """QCAlgorithm implementation of the RSI Momentum strategy.

    Mirrors src/strategies/rsi_momentum.py:
        BUY  — RSI crosses back above oversold level (default 30)
        SELL — RSI crosses above overbought level (default 70)

    Attributes
    ----------
    RSI_PERIOD : int
        Wilder smoothing period for RSI (default 14).
    OVERSOLD : float
        Buy signal threshold (default 30.0).
    OVERBOUGHT : float
        Sell signal threshold (default 70.0).
    SYMBOLS : list[str]
        Ticker basket matching Step 1 sign-off.
    """

    # ── Parameters (match config/settings.py) ───────────────────────────
    RSI_PERIOD: int = 14
    OVERSOLD: float = 30.0
    OVERBOUGHT: float = 70.0
    SYMBOLS = ["HSBA.L", "LLOY.L", "BP.L", "RIO.L", "GLEN.L"]

    # ── Lifecycle ────────────────────────────────────────────────────────

    def Initialize(self) -> None:  # noqa: N802
        """Set up algorithm parameters, universe, and indicators."""
        self.SetStartDate(2025, 1, 1)
        self.SetEndDate(2026, 1, 1)
        self.SetCash(100_000)

        self._rsi = {}
        self._prev_rsi = {}

        for ticker in self.SYMBOLS:
            equity = self.AddEquity(ticker, Resolution.Daily, Market.UK)
            sym = equity.Symbol
            self._rsi[sym] = self.RSI(
                sym, self.RSI_PERIOD, MovingAverageType.Wilders, Resolution.Daily
            )
            self._prev_rsi[sym] = None

        # Warm up: need RSI_PERIOD + 2 bars for two consecutive RSI values
        self.SetWarmUp(self.RSI_PERIOD + 2)

    def OnData(self, data) -> None:  # noqa: N802
        """Process daily bars — detect RSI level crossings and submit orders."""
        if self.IsWarmingUp:
            return

        for sym in list(self._rsi.keys()):
            if not data.ContainsKey(sym) or data[sym] is None:
                continue

            rsi_indicator = self._rsi[sym]
            if not rsi_indicator.IsReady:
                continue

            curr = rsi_indicator.Current.Value
            prev = self._prev_rsi[sym]

            if prev is not None:
                # Buy: RSI crosses above oversold level
                if prev < self.OVERSOLD <= curr:
                    strength = min(
                        (curr - self.OVERSOLD) / (50 - self.OVERSOLD), 1.0
                    )
                    strength = max(strength, 0.0)
                    qty = self._position_size(sym, data[sym].Close, strength)
                    if qty > 0:
                        self.MarketOrder(sym, qty)
                        self.Debug(
                            f"BUY  {sym} qty={qty} rsi={curr:.2f}"
                        )

                # Sell: RSI crosses above overbought level
                elif prev < self.OVERBOUGHT <= curr:
                    if self.Portfolio[sym].Invested:
                        self.Liquidate(sym)
                        self.Debug(f"SELL {sym} rsi={curr:.2f}")

            self._prev_rsi[sym] = curr

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
