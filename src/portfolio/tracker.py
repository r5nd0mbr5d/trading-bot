"""Portfolio tracker — aggregates positions and computes P&L metrics."""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.data.models import Position

logger = logging.getLogger(__name__)


class PortfolioTracker:
    """Tracks portfolio state and computes performance metrics."""

    def __init__(self, initial_capital: float = 100_000.0):
        self._initial_capital = initial_capital
        self._snapshots: List[Dict] = []

    @staticmethod
    def _fx_rate(
        from_currency: str,
        to_currency: str,
        fx_rates: Optional[Dict[str, float]] = None,
    ) -> float:
        src = (from_currency or "").upper()
        dst = (to_currency or "").upper()
        if not src or not dst or src == dst:
            return 1.0

        rates = fx_rates or {}
        direct_key = f"{src}_{dst}"
        if direct_key in rates and rates[direct_key] > 0:
            return float(rates[direct_key])

        inverse_key = f"{dst}_{src}"
        if inverse_key in rates and rates[inverse_key] > 0:
            return 1.0 / float(rates[inverse_key])

        logger.warning("Missing FX rate for %s->%s, using 1.0 fallback", src, dst)
        return 1.0

    def snapshot(
        self,
        positions: Dict[str, Position],
        cash: float,
        *,
        base_currency: str = "USD",
        symbol_currencies: Optional[Dict[str, str]] = None,
        cash_currency: Optional[str] = None,
        fx_rates: Optional[Dict[str, float]] = None,
    ) -> Dict:
        """Record current portfolio state. Call once per bar."""
        base = (base_currency or "USD").upper()
        sym_ccy = symbol_currencies or {}
        cash_ccy = (cash_currency or base).upper()

        market_value = 0.0
        unrealized_pnl = 0.0
        for sym, pos in positions.items():
            position_ccy = sym_ccy.get(sym, base)
            rate = self._fx_rate(position_ccy, base, fx_rates)
            market_value += pos.market_value * rate
            unrealized_pnl += pos.unrealized_pnl * rate

        cash_in_base = cash * self._fx_rate(cash_ccy, base, fx_rates)
        portfolio_value = cash_in_base + market_value

        snap = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "base_currency": base,
            "portfolio_value": round(portfolio_value, 2),
            "cash": round(cash_in_base, 2),
            "market_value": round(market_value, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "num_positions": len(positions),
            "return_pct": round(
                (portfolio_value - self._initial_capital) / self._initial_capital * 100, 4
            ),
        }
        self._snapshots.append(snap)
        return snap

    def current_return_pct(self, portfolio_value: float) -> float:
        return (portfolio_value - self._initial_capital) / self._initial_capital * 100

    def max_drawdown_pct(self) -> float:
        if len(self._snapshots) < 2:
            return 0.0
        values = [s["portfolio_value"] for s in self._snapshots]
        peak = values[0]
        max_dd = 0.0
        for v in values:
            peak = max(peak, v)
            dd = (peak - v) / peak
            max_dd = max(max_dd, dd)
        return round(max_dd * 100, 4)

    def print_summary(self, positions: Dict[str, Position], cash: float) -> None:
        snap = self.snapshot(positions, cash)
        print("\n--- Portfolio Summary ---")
        print(f"  Value:       ${snap['portfolio_value']:>12,.2f}")
        print(f"  Cash:        ${snap['cash']:>12,.2f}")
        print(f"  Market Val:  ${snap['market_value']:>12,.2f}")
        print(f"  Return:      {snap['return_pct']:>11.2f}%")
        print(f"  Unrealised:  ${snap['unrealized_pnl']:>12,.2f}")
        print(f"  Positions:   {snap['num_positions']}")
        if positions:
            print("\n  Open positions:")
            for sym, pos in positions.items():
                print(
                    f"    {sym:<8} qty={pos.qty:>8.2f}  "
                    f"entry=${pos.avg_entry_price:.2f}  "
                    f"now=${pos.current_price:.2f}  "
                    f"pnl={pos.unrealized_pnl_pct:.1%}"
                )
