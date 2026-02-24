"""FX rate staleness helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def evaluate_fx_staleness(
    pair: str,
    fx_rate_timestamps: Optional[Dict[str, str]],
    max_age_hours: Optional[float],
    *,
    now: Optional[datetime] = None,
) -> Dict[str, Optional[object]]:
    """Return staleness metadata for a single FX pair."""
    timestamps = fx_rate_timestamps or {}
    ts_raw = timestamps.get(pair)
    ts = _parse_timestamp(ts_raw)

    if now is None:
        now = datetime.now(timezone.utc)

    if ts is None:
        return {
            "timestamp": ts_raw,
            "age_hours": None,
            "stale": None,
            "note": "timestamp_missing",
        }

    age_hours = (now - ts).total_seconds() / 3600.0
    max_age = float(max_age_hours) if max_age_hours not in (None, 0) else None
    stale = age_hours > max_age if max_age is not None else None

    note = f"age_hours={age_hours:.1f}"
    if stale is True:
        note = f"stale_by_hours={age_hours:.1f}"

    return {
        "timestamp": ts.isoformat(),
        "age_hours": round(age_hours, 2),
        "stale": stale,
        "note": note,
    }
