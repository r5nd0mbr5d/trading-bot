"""Symbol-universe health checks for paper-trial startup.

This module evaluates whether enough configured symbols have recent bars and
optionally remediates by selecting a deterministic healthy subset.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from config.settings import Settings
from src.data.feeds import MarketDataFeed


def _count_bars(frame: pd.DataFrame) -> int:
    """Return the number of bars in a historical frame.

    Parameters
    ----------
    frame : pd.DataFrame
        Historical OHLCV frame returned by the data feed.

    Returns
    -------
    int
        Number of bars available in ``frame``.
    """
    return 0 if frame is None else int(len(frame.index))


def evaluate_symbol_universe_health(
    settings: Settings,
    *,
    feed: MarketDataFeed | None = None,
    symbols: list[str] | None = None,
) -> dict[str, Any]:
    """Evaluate data availability for the configured symbol universe.

    Parameters
    ----------
    settings : Settings
        Runtime settings containing symbol-health thresholds.
    feed : MarketDataFeed | None, optional
        Data feed implementation; when omitted, a new ``MarketDataFeed`` is
        created from ``settings``.
    symbols : list[str] | None, optional
        Symbols to evaluate; defaults to ``settings.data.symbols``.

    Returns
    -------
    dict[str, Any]
        Health summary including per-symbol outcomes and aggregate ratios.
    """
    active_symbols = list(symbols or settings.data.symbols)
    data_feed = feed or MarketDataFeed(settings)
    min_bars = max(int(settings.symbol_universe_min_bars_per_symbol), 1)
    period = settings.symbol_universe_preflight_period
    interval = settings.symbol_universe_preflight_interval

    symbol_rows: list[dict[str, Any]] = []
    healthy_symbols: list[str] = []

    for symbol in active_symbols:
        bars = 0
        error: str | None = None
        try:
            frame = data_feed.fetch_historical(symbol, period=period, interval=interval)
            bars = _count_bars(frame)
        except Exception as exc:  # pragma: no cover - exercised via tests with fake feed
            error = str(exc)

        is_healthy = bars >= min_bars
        if is_healthy:
            healthy_symbols.append(symbol)

        row = {
            "symbol": symbol,
            "bars": bars,
            "healthy": is_healthy,
            "error": error,
        }
        symbol_rows.append(row)

    total_symbols = len(active_symbols)
    healthy_count = len(healthy_symbols)
    ratio = (healthy_count / total_symbols) if total_symbols > 0 else 0.0
    threshold = float(settings.symbol_universe_min_availability_ratio)
    required_count = int(math.ceil(total_symbols * threshold)) if total_symbols > 0 else 0

    return {
        "total_symbols": total_symbols,
        "healthy_symbols": healthy_count,
        "availability_ratio": ratio,
        "threshold_ratio": threshold,
        "required_healthy_symbols": required_count,
        "min_bars_per_symbol": min_bars,
        "period": period,
        "interval": interval,
        "symbol_results": symbol_rows,
        "healthy_symbol_list": healthy_symbols,
    }


def apply_symbol_universe_policy(
    settings: Settings,
    *,
    feed: MarketDataFeed | None = None,
) -> dict[str, Any]:
    """Apply strict/remediation policy for paper-trial symbol data readiness.

    Parameters
    ----------
    settings : Settings
        Runtime settings containing policy switches and thresholds.
    feed : MarketDataFeed | None, optional
        Optional feed for deterministic tests.

    Returns
    -------
    dict[str, Any]
        Policy decision with fields ``allowed``, ``remediated``,
        ``selected_symbols``, and ``health_summary``.
    """
    health_summary = evaluate_symbol_universe_health(settings, feed=feed)
    configured_symbols = list(settings.data.symbols)
    healthy_symbol_list = list(health_summary["healthy_symbol_list"])
    ratio = float(health_summary["availability_ratio"])
    threshold = float(health_summary["threshold_ratio"])

    if ratio >= threshold:
        return {
            "allowed": True,
            "remediated": False,
            "selected_symbols": configured_symbols,
            "removed_symbols": [],
            "health_summary": health_summary,
            "reason": "threshold_met",
        }

    if not settings.symbol_universe_strict_mode:
        return {
            "allowed": True,
            "remediated": False,
            "selected_symbols": configured_symbols,
            "removed_symbols": [],
            "health_summary": health_summary,
            "reason": "strict_mode_disabled",
        }

    if not settings.symbol_universe_remediation_enabled:
        return {
            "allowed": False,
            "remediated": False,
            "selected_symbols": configured_symbols,
            "removed_symbols": [],
            "health_summary": health_summary,
            "reason": "insufficient_availability",
        }

    min_symbols = max(int(settings.symbol_universe_remediation_min_symbols), 1)
    if len(healthy_symbol_list) < min_symbols:
        return {
            "allowed": False,
            "remediated": False,
            "selected_symbols": configured_symbols,
            "removed_symbols": [],
            "health_summary": health_summary,
            "reason": "insufficient_healthy_symbols_for_remediation",
        }

    target_symbols = int(settings.symbol_universe_remediation_target_symbols)
    if target_symbols <= 0:
        selected_symbols = healthy_symbol_list
    else:
        selected_symbols = healthy_symbol_list[: max(target_symbols, min_symbols)]

    removed_symbols = [symbol for symbol in configured_symbols if symbol not in selected_symbols]

    return {
        "allowed": True,
        "remediated": True,
        "selected_symbols": selected_symbols,
        "removed_symbols": removed_symbols,
        "health_summary": health_summary,
        "reason": "remediated_with_healthy_subset",
    }
