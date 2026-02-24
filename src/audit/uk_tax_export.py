"""UK tax-oriented audit exports from SQLite audit_log."""

from __future__ import annotations

import csv
import json
import sqlite3
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Dict, List, Optional

from src.risk.fx_staleness import evaluate_fx_staleness


@dataclass
class TradeRow:
    timestamp: str
    symbol: str
    side: str
    qty: float
    price: float
    price_reference: float
    slippage_pct_vs_signal: float
    fee: float
    currency: str


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


def _extract_trade_rows(db_path: str) -> List[TradeRow]:
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("""
                SELECT timestamp, event_type, symbol, payload_json
                FROM audit_log
                WHERE event_type IN ('FILL', 'ORDER_FILLED', 'TRADE')
                ORDER BY timestamp ASC
                """).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower() and "audit_log" in str(exc).lower():
                return []
            raise

    trades: List[TradeRow] = []
    for row in rows:
        payload = {}
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}

        symbol = payload.get("symbol") or row["symbol"]
        if not symbol:
            continue

        side = str(payload.get("side", "")).lower()
        if side not in {"buy", "sell"}:
            continue

        qty = float(payload.get("qty", 0.0) or 0.0)
        price = float(payload.get("filled_price", payload.get("price", 0.0)) or 0.0)
        price_reference = float(payload.get("price_reference", payload.get("price", 0.0)) or 0.0)
        slippage_pct_vs_signal = float(payload.get("slippage_pct_vs_signal", 0.0) or 0.0)
        fee = float(payload.get("fee", payload.get("commission", 0.0)) or 0.0)
        currency = str(payload.get("currency") or _infer_currency(symbol)).upper()

        if qty <= 0 or price <= 0:
            continue

        trades.append(
            TradeRow(
                timestamp=str(row["timestamp"]),
                symbol=str(symbol),
                side=side,
                qty=qty,
                price=price,
                price_reference=price_reference,
                slippage_pct_vs_signal=slippage_pct_vs_signal,
                fee=fee,
                currency=currency,
            )
        )

    return trades


def export_uk_tax_reports(
    db_path: str,
    output_dir: str,
    *,
    base_currency: str = "GBP",
    fx_rates: Optional[Dict[str, float]] = None,
    fx_rate_timestamps: Optional[Dict[str, str]] = None,
    fx_rate_max_age_hours: Optional[float] = None,
) -> Dict[str, str]:
    """Export UK tax-oriented CSV reports from audit_log events.

    Returns file paths for:
      - trade_ledger.csv
      - realized_gains.csv
      - fx_notes.csv
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    trades = _extract_trade_rows(db_path)

    ledger_path = out / "trade_ledger.csv"
    realized_path = out / "realized_gains.csv"
    fx_notes_path = out / "fx_notes.csv"

    with ledger_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "timestamp",
                "symbol",
                "side",
                "qty",
                "price_reference",
                "price",
                "slippage_pct_vs_signal",
                "fee",
                "currency",
                f"gross_value_{base_currency.lower()}",
                f"fee_{base_currency.lower()}",
            ]
        )
        for t in trades:
            rate = _fx_rate(t.currency, base_currency, fx_rates)
            gross_base = t.qty * t.price * rate
            fee_base = t.fee * rate
            writer.writerow(
                [
                    t.timestamp,
                    t.symbol,
                    t.side,
                    round(t.qty, 6),
                    round(t.price_reference, 6),
                    round(t.price, 6),
                    round(t.slippage_pct_vs_signal, 8),
                    round(t.fee, 6),
                    t.currency,
                    round(gross_base, 6),
                    round(fee_base, 6),
                ]
            )

    lots: Dict[str, Deque[tuple[float, float, float]]] = defaultdict(deque)
    realized_rows: List[List[object]] = []
    for t in trades:
        rate = _fx_rate(t.currency, base_currency, fx_rates)
        fee_base = t.fee * rate
        if t.side == "buy":
            lots[t.symbol].append((t.qty, t.price * rate, fee_base))
            continue

        remaining = t.qty
        proceeds = t.qty * t.price * rate - fee_base
        matched_cost = 0.0
        while remaining > 0 and lots[t.symbol]:
            lot_qty, lot_unit_cost, lot_fee = lots[t.symbol][0]
            take = min(remaining, lot_qty)
            fee_alloc = lot_fee * (take / lot_qty) if lot_qty > 0 else 0.0
            matched_cost += take * lot_unit_cost + fee_alloc
            lot_qty -= take
            remaining -= take
            if lot_qty <= 1e-12:
                lots[t.symbol].popleft()
            else:
                lots[t.symbol][0] = (lot_qty, lot_unit_cost, lot_fee - fee_alloc)

        qty_matched = t.qty - remaining
        if qty_matched > 0:
            realized_rows.append(
                [
                    t.timestamp,
                    t.symbol,
                    round(qty_matched, 6),
                    round(proceeds, 6),
                    round(matched_cost, 6),
                    round(proceeds - matched_cost, 6),
                ]
            )

    with realized_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "timestamp",
                "symbol",
                "qty_matched",
                f"proceeds_{base_currency.lower()}",
                f"cost_basis_{base_currency.lower()}",
                f"realized_gain_{base_currency.lower()}",
            ]
        )
        for row in realized_rows:
            writer.writerow(row)

    used_pairs = sorted(
        {
            f"{t.currency}_{base_currency.upper()}"
            for t in trades
            if t.currency != base_currency.upper()
        }
    )
    with fx_notes_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["pair", "rate_used", "note"])
        for pair in used_pairs:
            src, dst = pair.split("_", 1)
            staleness = evaluate_fx_staleness(pair, fx_rate_timestamps, fx_rate_max_age_hours)
            note_parts = ["Configured rate or 1.0 fallback if missing"]
            if staleness.get("note"):
                note_parts.append(str(staleness["note"]))
            writer.writerow(
                [
                    pair,
                    round(_fx_rate(src, dst, fx_rates), 8),
                    "; ".join(note_parts),
                ]
            )

    return {
        "trade_ledger": str(ledger_path),
        "realized_gains": str(realized_path),
        "fx_notes": str(fx_notes_path),
    }
