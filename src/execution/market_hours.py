"""Exchange session helpers for paper/live trading safeguards."""

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo


def infer_exchange(symbol: str) -> str:
    sym = (symbol or "").upper()
    if sym.endswith(".L"):
        return "LSE"
    return "US"


def _is_weekday(dt: datetime) -> bool:
    return dt.weekday() < 5


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_market_open(symbol: str, timestamp_utc: datetime) -> bool:
    """Return True only during regular market session for the symbol's exchange."""
    ts_utc = _as_utc(timestamp_utc)
    exchange = infer_exchange(symbol)

    if exchange == "LSE":
        local = ts_utc.astimezone(ZoneInfo("Europe/London"))
        if not _is_weekday(local):
            return False
        local_time = local.time()
        return time(8, 0) <= local_time < time(16, 30)

    local = ts_utc.astimezone(ZoneInfo("America/New_York"))
    if not _is_weekday(local):
        return False
    local_time = local.time()
    return time(9, 30) <= local_time < time(16, 0)
