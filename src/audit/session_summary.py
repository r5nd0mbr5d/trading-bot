"""Paper session summary exports from SQLite audit_log."""

from __future__ import annotations

import csv
import json
import sqlite3
from collections import defaultdict, deque
from pathlib import Path
from typing import Deque, Dict, List, Optional, Tuple

from src.risk.fx_staleness import evaluate_fx_staleness


def _connect(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def _infer_currency(symbol: str) -> str:
    if (symbol or "").upper().endswith(".L"):
        return "GBP"
    return "USD"


def _fx_rate(from_currency: str, to_currency: str, fx_rates: Optional[Dict[str, float]]) -> float:
    src = (from_currency or "").upper()
    dst = (to_currency or "").upper()
    if src == dst:
        return 1.0
    rates = fx_rates or {}
    direct = f"{src}_{dst}"
    if direct in rates and rates[direct] > 0:
        return float(rates[direct])
    inverse = f"{dst}_{src}"
    if inverse in rates and rates[inverse] > 0:
        return 1.0 / float(rates[inverse])
    return 1.0


def _fx_rate_with_metadata(
    from_currency: str,
    to_currency: str,
    fx_rates: Optional[Dict[str, float]],
) -> Tuple[float, bool, Optional[str]]:
    src = (from_currency or "").upper()
    dst = (to_currency or "").upper()
    if src == dst:
        return 1.0, False, None

    rate = _fx_rate(src, dst, fx_rates)
    rates = fx_rates or {}
    direct = f"{src}_{dst}"
    inverse = f"{dst}_{src}"
    has_rate = (direct in rates and rates[direct] > 0) or (inverse in rates and rates[inverse] > 0)
    return rate, not has_rate, direct


def _load_events(db_path: str) -> List[sqlite3.Row]:
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute("""
                SELECT timestamp, event_type, symbol, payload_json
                FROM audit_log
                ORDER BY timestamp ASC
                """).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower() and "audit_log" in str(exc).lower():
                return []
            raise


def summarize_paper_session(
    db_path: str,
    *,
    base_currency: str = "GBP",
    fx_rates: Optional[Dict[str, float]] = None,
    fx_rate_timestamps: Optional[Dict[str, str]] = None,
    fx_rate_max_age_hours: Optional[float] = None,
) -> dict:
    """Compute high-level execution metrics from audit events."""
    events = _load_events(db_path)
    fills: List[dict] = []

    signal_count = 0
    order_attempt_count = 0

    for row in events:
        event_type = str(row["event_type"])
        if event_type == "SIGNAL":
            signal_count += 1
        elif event_type == "ORDER_SUBMITTED":
            order_attempt_count += 1

        if event_type not in {"FILL", "ORDER_FILLED", "TRADE"}:
            continue

        try:
            payload = json.loads(row["payload_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}

        side = str(payload.get("side", "")).lower()
        qty = float(payload.get("qty", 0.0) or 0.0)
        price = float(payload.get("filled_price", payload.get("price", 0.0)) or 0.0)
        fee = float(payload.get("fee", payload.get("commission", 0.0)) or 0.0)
        slippage_pct = float(payload.get("slippage_pct_vs_signal", 0.0) or 0.0)
        symbol = str(payload.get("symbol") or row["symbol"] or "")
        currency = str(payload.get("currency") or _infer_currency(symbol)).upper()

        if side not in {"buy", "sell"} or qty <= 0 or price <= 0 or not symbol:
            continue

        fills.append(
            {
                "timestamp": str(row["timestamp"]),
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "price": price,
                "fee": fee,
                "currency": currency,
                "slippage_pct_vs_signal": slippage_pct,
            }
        )

    filled_order_count = len(fills)
    fill_rate = (filled_order_count / order_attempt_count) if order_attempt_count > 0 else 0.0
    avg_slippage_pct = (
        sum(f["slippage_pct_vs_signal"] for f in fills) / filled_order_count
        if filled_order_count > 0
        else 0.0
    )
    avg_fee_per_trade = (
        sum(f["fee"] for f in fills) / filled_order_count if filled_order_count > 0 else 0.0
    )

    lots: Dict[str, Deque[tuple[float, float, float]]] = defaultdict(deque)
    closed_trade_pnls: List[float] = []
    fx_converted_fill_count = 0
    fx_fallback_count = 0
    fx_missing_pairs: set[str] = set()
    for fill in fills:
        rate, used_fallback, pair = _fx_rate_with_metadata(
            fill["currency"], base_currency, fx_rates
        )
        if pair:
            fx_converted_fill_count += 1
            if used_fallback:
                fx_fallback_count += 1
                fx_missing_pairs.add(pair)
        fee_base = fill["fee"] * rate
        unit_price_base = fill["price"] * rate
        if fill["side"] == "buy":
            lots[fill["symbol"]].append((fill["qty"], unit_price_base, fee_base))
            continue

        remaining = fill["qty"]
        proceeds = fill["qty"] * unit_price_base - fee_base
        matched_cost = 0.0
        while remaining > 0 and lots[fill["symbol"]]:
            lot_qty, lot_unit_cost, lot_fee = lots[fill["symbol"]][0]
            take = min(remaining, lot_qty)
            fee_alloc = lot_fee * (take / lot_qty) if lot_qty > 0 else 0.0
            matched_cost += take * lot_unit_cost + fee_alloc
            lot_qty -= take
            remaining -= take
            if lot_qty <= 1e-12:
                lots[fill["symbol"]].popleft()
            else:
                lots[fill["symbol"]][0] = (lot_qty, lot_unit_cost, lot_fee - fee_alloc)

        qty_matched = fill["qty"] - remaining
        if qty_matched > 0:
            pnl = proceeds - matched_cost
            closed_trade_pnls.append(pnl)

    realized_pnl = sum(closed_trade_pnls)
    profitable_trades = sum(1 for pnl in closed_trade_pnls if pnl > 0)
    closed_trade_count = len(closed_trade_pnls)
    win_rate = (profitable_trades / closed_trade_count) if closed_trade_count > 0 else 0.0
    gross_profit = sum(pnl for pnl in closed_trade_pnls if pnl > 0)
    gross_loss_abs = abs(sum(pnl for pnl in closed_trade_pnls if pnl < 0))
    profit_factor = (
        gross_profit / gross_loss_abs
        if gross_loss_abs > 0
        else (float("inf") if gross_profit > 0 else 0.0)
    )

    first_ts = str(events[0]["timestamp"]) if events else None
    last_ts = str(events[-1]["timestamp"]) if events else None

    used_pairs = sorted(
        {
            f"{f['currency']}_{base_currency.upper()}"
            for f in fills
            if f["currency"] != base_currency.upper()
        }
    )
    fx_rate_staleness = {}
    fx_rate_stale_pairs = []
    for pair in used_pairs:
        status = evaluate_fx_staleness(pair, fx_rate_timestamps, fx_rate_max_age_hours)
        fx_rate_staleness[pair] = status
        if status.get("stale") is True:
            fx_rate_stale_pairs.append(pair)

    return {
        "db_path": db_path,
        "base_currency": base_currency,
        "event_count": len(events),
        "signal_count": signal_count,
        "order_attempt_count": order_attempt_count,
        "filled_order_count": filled_order_count,
        "fill_rate": round(fill_rate, 6),
        "avg_slippage_pct": round(avg_slippage_pct, 8),
        "avg_fee_per_trade": round(avg_fee_per_trade, 6),
        "closed_trade_count": closed_trade_count,
        "win_rate": round(win_rate, 6),
        "realized_pnl": round(realized_pnl, 6),
        "profit_factor": round(profit_factor, 6) if profit_factor != float("inf") else "inf",
        "first_event_ts": first_ts,
        "last_event_ts": last_ts,
        "fx_converted_fill_count": fx_converted_fill_count,
        "fx_fallback_count": fx_fallback_count,
        "fx_missing_pairs": sorted(fx_missing_pairs),
        "fx_rate_staleness": fx_rate_staleness,
        "fx_rate_stale_pairs": fx_rate_stale_pairs,
    }


def export_paper_session_summary(
    db_path: str,
    output_dir: str,
    *,
    base_currency: str = "GBP",
    fx_rates: Optional[Dict[str, float]] = None,
    fx_rate_timestamps: Optional[Dict[str, str]] = None,
    fx_rate_max_age_hours: Optional[float] = None,
) -> dict:
    """Write paper session summary metrics to JSON and CSV."""
    summary = summarize_paper_session(
        db_path,
        base_currency=base_currency,
        fx_rates=fx_rates,
        fx_rate_timestamps=fx_rate_timestamps,
        fx_rate_max_age_hours=fx_rate_max_age_hours,
    )
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / "paper_session_summary.json"
    csv_path = out / "paper_session_summary.csv"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        for key, value in summary.items():
            writer.writerow([key, value])

    return {
        "summary": summary,
        "json_path": str(json_path),
        "csv_path": str(csv_path),
    }
