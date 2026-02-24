"""Backtesting engine — zero lookahead bias bar replay.

Replays historical OHLCV data through a strategy + risk manager,
using PaperBroker for in-memory fills.

Usage:
    from config.settings import Settings
    from src.strategies.ma_crossover import MACrossoverStrategy
    from backtest.engine import BacktestEngine

    settings = Settings()
    strategy = MACrossoverStrategy(settings)
    engine = BacktestEngine(settings, strategy)
    results = engine.run("2022-01-01", "2024-01-01")
    results.print_report()
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

import pandas as pd

from config.settings import Settings
from src.data.feeds import MarketDataFeed
from src.data.models import Bar, Signal
from src.execution.broker import PaperBroker
from src.risk.manager import RiskManager
from src.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


@dataclass
class EquityPoint:
    timestamp: datetime
    portfolio_value: float
    cash: float
    num_positions: int


@dataclass
class BacktestResults:
    equity_curve: List[EquityPoint] = field(default_factory=list)
    trades: List[Dict] = field(default_factory=list)
    signals: List[Signal] = field(default_factory=list)
    initial_capital: float = 0.0
    final_value: float = 0.0
    risk_free_rate: float = 0.0  # Annualised; injected from Settings

    @property
    def total_return_pct(self) -> float:
        if self.initial_capital == 0:
            return 0.0
        return (self.final_value - self.initial_capital) / self.initial_capital * 100

    @property
    def sharpe_ratio(self) -> float:
        """Annualised Sharpe (daily bars, configurable risk-free rate)."""
        if len(self.equity_curve) < 2:
            return 0.0
        values = pd.Series([e.portfolio_value for e in self.equity_curve])
        returns = values.pct_change().dropna()
        if returns.std() == 0:
            return 0.0
        excess_returns = returns - self.risk_free_rate / 252
        return (excess_returns.mean() / returns.std()) * (252**0.5)

    @property
    def max_drawdown_pct(self) -> float:
        if not self.equity_curve:
            return 0.0
        values = pd.Series([e.portfolio_value for e in self.equity_curve])
        rolling_max = values.cummax()
        drawdown = (values - rolling_max) / rolling_max
        return abs(float(drawdown.min())) * 100

    @property
    def win_rate(self) -> float:
        """Fraction of sell trades that were profitable."""
        sells = [t for t in self.trades if t["side"] == "sell" and t.get("pnl") is not None]
        if not sells:
            return 0.0
        wins = sum(1 for t in sells if t["pnl"] > 0)
        return wins / len(sells)

    def print_report(self) -> None:
        print("\n" + "=" * 60)
        print("  BACKTEST RESULTS")
        print("=" * 60)
        print(f"  Initial Capital : ${self.initial_capital:>12,.2f}")
        print(f"  Final Value     : ${self.final_value:>12,.2f}")
        print(f"  Total Return    : {self.total_return_pct:>11.2f}%")
        print(f"  Sharpe Ratio    : {self.sharpe_ratio:>12.2f}")
        print(f"  Max Drawdown    : {self.max_drawdown_pct:>11.2f}%")
        print(f"  Total Signals   : {len(self.signals):>12}")
        print(f"  Total Trades    : {len(self.trades):>12}")
        print("=" * 60 + "\n")
        if self.trades:
            print("Last 10 trades:")
            header = f"  {'Date':<12} {'Symbol':<8} {'Side':<6} {'Qty':>8} {'Price':>10}"
            print(header)
            print("  " + "-" * (len(header) - 2))
            for t in self.trades[-10:]:
                price_str = f"${t['price']:,.2f}" if t.get("price") else "N/A"
                print(
                    f"  {str(t['date'])[:10]:<12} {t['symbol']:<8} "
                    f"{t['side']:<6} {t['qty']:>8.2f} {price_str:>10}"
                )
            print()


class BacktestEngine:

    def __init__(self, settings: Settings, strategy: BaseStrategy):
        self.settings = settings
        self.strategy = strategy
        self.risk = RiskManager(settings)
        self.broker = PaperBroker(initial_cash=settings.initial_capital)
        self.feed = MarketDataFeed(settings)

    def run(self, start: str, end: str) -> BacktestResults:
        symbols = self.settings.data.symbols
        logger.info(f"Backtest: {symbols}  {start} -> {end}")

        # Fetch all data upfront using explicit date range (more reliable than period="max")
        all_data: Dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            df = self.feed.fetch_historical(symbol, interval="1d", start=start, end=end)
            all_data[symbol] = df

        all_dates = sorted(set().union(*[set(df.index) for df in all_data.values()]))

        results = BacktestResults(
            initial_capital=self.settings.initial_capital,
            risk_free_rate=self.settings.risk_free_rate,
        )
        entry_prices: Dict[str, float] = {}
        # Orders buffered at bar[t] close, filled at bar[t+1] open
        pending_orders: list = []

        slippage = self.settings.broker.slippage_pct
        commission_per_share = self.settings.broker.commission_per_share

        for date in all_dates:
            open_prices: Dict[str, float] = {}
            close_prices: Dict[str, float] = {}

            for symbol, df in all_data.items():
                if date not in df.index:
                    continue
                row = df.loc[date]
                open_prices[symbol] = float(row["open"])
                close_prices[symbol] = float(row["close"])

            # --- Fill pending orders from previous bar at today's open ---
            still_pending: list = []
            for entry in pending_orders:
                order = entry["order"]
                sym = order.symbol
                if sym not in open_prices:
                    still_pending.append(entry)
                    continue
                raw_open = open_prices[sym]
                if order.side.value == "buy":
                    fill_price = raw_open * (1 + slippage)
                else:
                    fill_price = raw_open * (1 - slippage)
                commission = order.qty * commission_per_share
                filled = self.broker.fill_order_at_price(order, fill_price, commission)
                trade = {
                    "date": date,
                    "symbol": sym,
                    "side": filled.side.value,
                    "qty": filled.qty,
                    "price": filled.filled_price,
                    "status": filled.status.value,
                    "pnl": None,
                }
                if filled.side.value == "buy":
                    entry_prices[sym] = filled.filled_price or fill_price
                elif filled.side.value == "sell" and sym in entry_prices:
                    pnl = ((filled.filled_price or fill_price) - entry_prices[sym]) * filled.qty
                    trade["pnl"] = pnl
                    self.risk.record_trade_result(is_profitable=pnl > 0)
                    del entry_prices[sym]
                results.trades.append(trade)
            pending_orders = still_pending

            # --- Generate signals for this bar using only current-bar data ---
            for symbol, df in all_data.items():
                if date not in df.index:
                    continue
                row = df.loc[date]
                bar = Bar(
                    symbol=symbol,
                    timestamp=date.to_pydatetime() if hasattr(date, "to_pydatetime") else date,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume", 0)),
                )
                signal = self.strategy.on_bar(bar)
                if signal:
                    results.signals.append(signal)
                    order = self.risk.approve_signal(
                        signal,
                        self.broker.get_portfolio_value(),
                        close_prices.get(symbol, 0),
                        self.broker.get_positions(),
                    )
                    if order:
                        # Buffer — will fill at next bar's open
                        pending_orders.append({"order": order})

            # Update positions to close prices for end-of-bar valuation
            self.broker.update_prices(close_prices)
            current_value = self.broker.get_portfolio_value()
            results.equity_curve.append(
                EquityPoint(
                    timestamp=date.to_pydatetime() if hasattr(date, "to_pydatetime") else date,
                    portfolio_value=current_value,
                    cash=self.broker.get_cash(),
                    num_positions=len(self.broker.get_positions()),
                )
            )
            # Feed daily return into the VaR tracker
            if len(results.equity_curve) >= 2:
                prev_value = results.equity_curve[-2].portfolio_value
                if prev_value > 0:
                    self.risk.update_portfolio_return((current_value - prev_value) / prev_value)

        results.final_value = self.broker.get_portfolio_value()
        return results
