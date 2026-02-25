"""Slippage and commission modelling for backtests."""

from __future__ import annotations

from dataclasses import dataclass
import math

from config.settings import SlippageConfig


@dataclass
class SlippageProfile:
    """Preset profile values for slippage assumptions."""

    spread_bps: float
    impact_bps: float
    commission_min: float | None = None


class SlippageModel:
    """Estimate execution slippage and commission costs."""

    _PROFILES: dict[str, SlippageProfile] = {
        "optimistic": SlippageProfile(spread_bps=2.0, impact_bps=4.0),
        "realistic": SlippageProfile(spread_bps=8.0, impact_bps=12.0),
        "pessimistic": SlippageProfile(spread_bps=20.0, impact_bps=30.0),
        "crypto": SlippageProfile(spread_bps=50.0, impact_bps=75.0, commission_min=0.0),
    }

    def __init__(self, config: SlippageConfig):
        self._config = config

    def _resolved_profile(self) -> SlippageProfile:
        preset = str(self._config.preset or "realistic").strip().lower()
        profile = self._PROFILES.get(preset)
        if profile is None:
            return SlippageProfile(
                spread_bps=float(self._config.spread_bps),
                impact_bps=float(self._config.impact_bps),
            )
        return profile

    def estimate_slippage_pct(self, order_size: float, average_daily_volume: float) -> float:
        """Return fractional slippage (e.g. 0.001 = 0.1%)."""
        adv = max(float(average_daily_volume), 1.0)
        size = max(float(order_size), 0.0)
        ratio = size / adv

        profile = self._resolved_profile()
        spread_component = (profile.spread_bps / 10_000.0) * ratio

        impact_component = 0.0
        if ratio > float(self._config.impact_threshold_adv_frac):
            impact_component = (profile.impact_bps / 10_000.0) * math.sqrt(ratio)

        return max(0.0, spread_component + impact_component)

    def estimate_fill_price(
        self,
        side: str,
        reference_price: float,
        order_size: float,
        average_daily_volume: float,
    ) -> float:
        """Return fill price adjusted by estimated slippage."""
        base_price = max(float(reference_price), 0.0)
        slip = self.estimate_slippage_pct(order_size, average_daily_volume)

        if side.strip().lower() == "buy":
            return base_price * (1.0 + slip)
        return base_price * (1.0 - slip)

    def estimate_commission(self, order_size: float, fill_price: float) -> float:
        """IBKR UK commission model: 0.05% notional, min £1.70 per trade."""
        notional = max(float(order_size), 0.0) * max(float(fill_price), 0.0)
        proportional = notional * float(self._config.commission_rate)
        profile = self._resolved_profile()
        commission_floor = (
            float(profile.commission_min)
            if profile.commission_min is not None
            else float(self._config.commission_min)
        )
        return max(commission_floor, proportional)
