"""Paper-trading-only runtime guardrails.

Enforces safety constraints that are specific to paper trading and would
not apply to backtests. All checks return a reason string (empty = pass).
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config.settings import PaperGuardrailsConfig


class PaperGuardrails:
    """Enforce paper-trading safeguards: order limits, reject tracking, session windows."""

    def __init__(self, config: PaperGuardrailsConfig):
        """Initialize guardrails with configuration."""
        self.config = config
        self.orders_today: list[datetime] = []  # Track order timestamps
        self.rejects_recent: list[datetime] = []  # Track reject timestamps (last hour)
        self.symbol_cooldown: Dict[str, datetime] = {}  # symbol -> cooldown_until
        self.consecutive_rejects: int = 0
        self.last_reject_time: Optional[datetime] = None

    def check_daily_order_limit(self) -> str:
        """Return reason if daily order limit exceeded, else empty string."""
        if self.config.skip_daily_limit or not self.config.enabled:
            return ""

        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Remove orders from previous days
        self.orders_today = [t for t in self.orders_today if t >= today_start]

        if len(self.orders_today) > self.config.max_orders_per_day:
            return f"daily_order_limit_exceeded: {len(self.orders_today)} > {self.config.max_orders_per_day}"

        return ""

    def check_reject_rate(self) -> str:
        """Return reason if reject rate exceeded, else empty string."""
        if self.config.skip_reject_rate or not self.config.enabled:
            return ""

        now = datetime.now(timezone.utc)
        one_hour_ago = now - timedelta(hours=1)

        # Remove rejects older than 1 hour
        self.rejects_recent = [t for t in self.rejects_recent if t >= one_hour_ago]

        if len(self.rejects_recent) > self.config.max_rejects_per_hour:
            return f"reject_rate_exceeded: {len(self.rejects_recent)} > {self.config.max_rejects_per_hour} in 1 hour"

        return ""

    def check_symbol_cooldown(self, symbol: str) -> str:
        """Return reason if symbol is in cooldown, else empty string."""
        if self.config.skip_cooldown or not self.config.enabled:
            return ""

        now = datetime.now(timezone.utc)

        if symbol in self.symbol_cooldown:
            cooldown_until = self.symbol_cooldown[symbol]
            if now < cooldown_until:
                remaining = int((cooldown_until - now).total_seconds())
                return f"symbol_cooldown_active: {symbol} cooldown ends in {remaining}s"
            else:
                # Cooldown expired, remove it
                del self.symbol_cooldown[symbol]

        return ""

    def check_session_window(self, symbol: str = "", is_crypto: bool = False) -> str:
        """Return reason if outside trading session window, else empty string."""
        if self.config.skip_session_window or not self.config.enabled:
            return ""

        if is_crypto and self.config.skip_session_window_for_crypto:
            return ""

        now_utc = self._now_utc()
        hour, tz_name = self._session_hour(now_utc)

        if hour < self.config.session_start_hour or hour >= self.config.session_end_hour:
            return (
                "outside_session_window: "
                f"{hour:02d}:00 {tz_name} "
                f"(allowed {self.config.session_start_hour:02d}-{self.config.session_end_hour:02d} {tz_name}; "
                f"now_utc={now_utc:%H:%M})"
            )

        return ""

    def _now_utc(self) -> datetime:
        now = datetime.now(timezone.utc)
        if now.tzinfo is None:
            return now.replace(tzinfo=timezone.utc)
        return now

    def _session_hour(self, now_utc: datetime) -> tuple[int, str]:
        timezone_name = (self.config.session_timezone or "UTC").strip() or "UTC"
        try:
            session_tz = ZoneInfo(timezone_name)
            now_local = now_utc.astimezone(session_tz)
            return now_local.hour, timezone_name
        except (ZoneInfoNotFoundError, ValueError):
            return now_utc.hour, "UTC"

    def should_auto_stop(self) -> str:
        """Return reason to halt trading, else empty string."""
        if self.config.skip_auto_stop or not self.config.enabled:
            return ""

        if self.consecutive_rejects > self.config.max_consecutive_rejects:
            return f"auto_stop_consecutive_rejects: {self.consecutive_rejects} > {self.config.max_consecutive_rejects}"

        return ""

    def all_checks(self, symbol: str, is_crypto: bool = False) -> list[str]:
        """Run all checks and return list of reasons for any that fail."""
        reasons = []

        if daily_reason := self.check_daily_order_limit():
            reasons.append(daily_reason)
        if reject_reason := self.check_reject_rate():
            reasons.append(reject_reason)
        if cooldown_reason := self.check_symbol_cooldown(symbol):
            reasons.append(cooldown_reason)
        if session_reason := self.check_session_window(symbol=symbol, is_crypto=is_crypto):
            reasons.append(session_reason)
        if stop_reason := self.should_auto_stop():
            reasons.append(stop_reason)

        return reasons

    def record_order(self) -> None:
        """Record that an order was submitted."""
        self.orders_today.append(datetime.now(timezone.utc))

    def record_reject(self, symbol: str) -> None:
        """Record that an order was rejected."""
        now = datetime.now(timezone.utc)
        self.rejects_recent.append(now)

        # Set symbol cooldown
        self.symbol_cooldown[symbol] = now + timedelta(seconds=self.config.reject_cooldown_seconds)

        # Update consecutive rejects
        if self.last_reject_time is not None:
            elapsed = (now - self.last_reject_time).total_seconds()
            if elapsed <= self.config.consecutive_reject_reset_minutes * 60:
                self.consecutive_rejects += 1
            else:
                # Reset if too much time has passed
                self.consecutive_rejects = 1
        else:
            self.consecutive_rejects = 1

        self.last_reject_time = now

    def reset_reject_counter(self) -> None:
        """Manually reset consecutive reject counter (e.g., on fill)."""
        self.consecutive_rejects = 0
        self.last_reject_time = None
