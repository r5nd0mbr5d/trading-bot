"""Data quality guardrails for live/paper bars."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List

logger = logging.getLogger(__name__)


class DataQualityGuard:
    """Detect stale bars and large session gaps."""

    def __init__(
        self,
        *,
        max_bar_age_seconds: int = 600,
        max_bar_gap_seconds: int = 3600,
        max_consecutive_stale: int = 3,
        session_gap_skip_bars: int = 1,
    ) -> None:
        self.max_bar_age_seconds = max_bar_age_seconds
        self.max_bar_gap_seconds = max_bar_gap_seconds
        self.max_consecutive_stale = max_consecutive_stale
        self.session_gap_skip_bars = session_gap_skip_bars
        self._last_bar_ts: Dict[str, datetime] = {}
        self._stale_counts: Dict[str, int] = {}
        self._gap_skip_remaining: Dict[str, int] = {}

    def check_bar(self, symbol: str, bar_ts: datetime, now_utc: datetime) -> List[str]:
        reasons: List[str] = []
        ts = (
            bar_ts.astimezone(timezone.utc)
            if bar_ts.tzinfo
            else bar_ts.replace(tzinfo=timezone.utc)
        )
        now = (
            now_utc.astimezone(timezone.utc)
            if now_utc.tzinfo
            else now_utc.replace(tzinfo=timezone.utc)
        )

        age_seconds = (now - ts).total_seconds()
        if age_seconds > self.max_bar_age_seconds:
            count = self._stale_counts.get(symbol, 0) + 1
            self._stale_counts[symbol] = count
            reasons.append(f"stale_bar_age_seconds:{int(age_seconds)}")
            logger.debug(
                f"Stale bar for {symbol}: age={int(age_seconds)}s (threshold={self.max_bar_age_seconds}s), "
                f"bar_ts={ts.isoformat()}, now={now.isoformat()}, count={count}/{self.max_consecutive_stale}"
            )
            if count >= self.max_consecutive_stale:
                reasons.append("stale_data_max_consecutive")
                logger.warning(
                    f"KILL SWITCH TRIGGERED for {symbol}: {count} consecutive stale bars. "
                    f"Last bar: {ts.isoformat()}, current time: {now.isoformat()}"
                )
        else:
            self._stale_counts[symbol] = 0

        last_ts = self._last_bar_ts.get(symbol)
        if last_ts is not None:
            gap_seconds = (ts - last_ts).total_seconds()
            if gap_seconds > self.max_bar_gap_seconds:
                self._gap_skip_remaining[symbol] = self.session_gap_skip_bars
                reasons.append(f"session_gap_seconds:{int(gap_seconds)}")

        if self._gap_skip_remaining.get(symbol, 0) > 0:
            self._gap_skip_remaining[symbol] -= 1
            reasons.append("session_gap_skip_bar")

        self._last_bar_ts[symbol] = ts
        return reasons
