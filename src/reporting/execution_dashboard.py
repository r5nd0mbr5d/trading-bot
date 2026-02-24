"""Execution telemetry dashboard export from SQLite audit events."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _connect(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    text = str(ts).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


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


def _safe_json_load(text: Optional[str]) -> Dict[str, Any]:
    try:
        return json.loads(text or "{}")
    except json.JSONDecodeError:
        return {}


def _pct(numerator: int, denominator: int) -> float:
    return (numerator / denominator) if denominator > 0 else 0.0


def _pctl(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(round((len(ordered) - 1) * p))
    idx = max(0, min(idx, len(ordered) - 1))
    return float(ordered[idx])


def _compute_metrics(rows: List[sqlite3.Row]) -> Dict[str, Any]:
    now_utc = datetime.now(timezone.utc)
    today = now_utc.date()
    day_labels = [(today - timedelta(days=delta)).isoformat() for delta in range(6, -1, -1)]

    submitted_by_day = {day: 0 for day in day_labels}
    filled_by_day = {day: 0 for day in day_labels}

    submitted_by_symbol: Dict[str, int] = defaultdict(int)
    rejected_by_symbol: Dict[str, int] = defaultdict(int)

    slippage_values: List[float] = []

    submitted_by_order_id: Dict[str, datetime] = {}
    submitted_queue_by_symbol: Dict[str, deque[datetime]] = defaultdict(deque)
    latency_by_hour: Dict[int, List[float]] = defaultdict(list)

    for row in rows:
        event_type = str(row["event_type"] or "")
        symbol = str(row["symbol"] or "")
        payload = _safe_json_load(row["payload_json"])
        ts = _parse_ts(str(row["timestamp"] or ""))
        if ts is None:
            continue

        day_key = ts.date().isoformat()

        payload_symbol = str(payload.get("symbol") or "")
        event_symbol = payload_symbol or symbol

        if event_type == "ORDER_SUBMITTED":
            if day_key in submitted_by_day:
                submitted_by_day[day_key] += 1
            if event_symbol:
                submitted_by_symbol[event_symbol] += 1

            order_id = str(payload.get("order_id") or "").strip()
            if order_id:
                submitted_by_order_id[order_id] = ts
            if event_symbol:
                submitted_queue_by_symbol[event_symbol].append(ts)

        elif event_type == "ORDER_FILLED":
            if day_key in filled_by_day:
                filled_by_day[day_key] += 1

            slippage = payload.get("slippage_pct_vs_signal")
            try:
                if slippage is not None:
                    slippage_values.append(float(slippage))
            except (TypeError, ValueError):
                pass

            order_id = str(payload.get("order_id") or "").strip()
            submitted_ts = submitted_by_order_id.pop(order_id, None) if order_id else None
            if submitted_ts is None and event_symbol and submitted_queue_by_symbol[event_symbol]:
                submitted_ts = submitted_queue_by_symbol[event_symbol].popleft()

            if submitted_ts is not None:
                latency = (ts - submitted_ts).total_seconds()
                if latency >= 0:
                    latency_by_hour[submitted_ts.hour].append(latency)

        elif event_type in {"ORDER_REJECTED", "ORDER_NOT_FILLED"}:
            if event_symbol:
                rejected_by_symbol[event_symbol] += 1

    fill_rate_trend = []
    for day in day_labels:
        submitted = submitted_by_day[day]
        filled = filled_by_day[day]
        fill_rate_trend.append(
            {
                "date": day,
                "submitted": submitted,
                "filled": filled,
                "fill_rate": round(_pct(filled, submitted), 6),
            }
        )

    symbol_set = sorted(set(submitted_by_symbol) | set(rejected_by_symbol))
    reject_rate_by_symbol = []
    for sym in symbol_set:
        submitted = submitted_by_symbol[sym]
        rejected = rejected_by_symbol[sym]
        reject_rate_by_symbol.append(
            {
                "symbol": sym,
                "submitted": submitted,
                "rejected": rejected,
                "reject_rate": round(_pct(rejected, submitted), 6),
            }
        )

    slippage_distribution = {
        "count": len(slippage_values),
        "p50": round(_pctl(slippage_values, 0.50), 8),
        "p95": round(_pctl(slippage_values, 0.95), 8),
        "max": round(max(slippage_values), 8) if slippage_values else 0.0,
    }

    latency_by_hour_rows = []
    for hour in sorted(latency_by_hour.keys()):
        samples = latency_by_hour[hour]
        latency_by_hour_rows.append(
            {
                "hour": hour,
                "count": len(samples),
                "avg_seconds": round(sum(samples) / len(samples), 4),
                "p95_seconds": round(_pctl(samples, 0.95), 4),
                "max_seconds": round(max(samples), 4),
            }
        )

    return {
        "event_count": len(rows),
        "generated_at": now_utc.isoformat(),
        "fill_rate_trend_7d": fill_rate_trend,
        "reject_rate_by_symbol": reject_rate_by_symbol,
        "slippage_distribution": slippage_distribution,
        "order_latency_by_hour": latency_by_hour_rows,
    }


def _render_html(metrics: Dict[str, Any], refresh_seconds: int) -> str:
    payload = json.dumps(metrics, separators=(",", ":"))
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <meta http-equiv=\"refresh\" content=\"{max(refresh_seconds, 5)}\" />
  <title>Execution Dashboard</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; color: #1f2937; }}
    h1 {{ margin-bottom: 0; }}
    .sub {{ color: #6b7280; margin-top: 4px; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(360px, 1fr)); gap: 16px; margin-top: 16px; }}
    .card {{ border: 1px solid #d1d5db; border-radius: 8px; padding: 12px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
    th, td {{ border-bottom: 1px solid #e5e7eb; text-align: left; padding: 6px; font-size: 13px; }}
    th {{ background: #f9fafb; }}
    .kpi {{ display: flex; gap: 16px; margin-top: 8px; }}
    .kpi-item {{ background: #f9fafb; border-radius: 6px; padding: 8px 10px; }}
    .mono {{ font-family: Consolas, monospace; }}
  </style>
</head>
<body>
  <h1>Execution Dashboard</h1>
  <div class=\"sub\">Auto-refresh every {max(refresh_seconds, 5)}s • Generated <span id=\"generated-at\"></span></div>

  <div class=\"grid\">
    <section class=\"card\">
      <h2>Fill Rate Trend (7D)</h2>
      <table id=\"fill-rate\">
        <thead><tr><th>Date</th><th>Submitted</th><th>Filled</th><th>Fill Rate</th></tr></thead>
        <tbody></tbody>
      </table>
    </section>

    <section class=\"card\">
      <h2>Reject Rate by Symbol</h2>
      <table id=\"reject-rate\">
        <thead><tr><th>Symbol</th><th>Submitted</th><th>Rejected</th><th>Reject Rate</th></tr></thead>
        <tbody></tbody>
      </table>
    </section>

    <section class=\"card\">
      <h2>Slippage Distribution</h2>
      <div class=\"kpi\">
        <div class=\"kpi-item\"><strong>Count</strong><div class=\"mono\" id=\"sl-count\"></div></div>
        <div class=\"kpi-item\"><strong>p50</strong><div class=\"mono\" id=\"sl-p50\"></div></div>
        <div class=\"kpi-item\"><strong>p95</strong><div class=\"mono\" id=\"sl-p95\"></div></div>
        <div class=\"kpi-item\"><strong>max</strong><div class=\"mono\" id=\"sl-max\"></div></div>
      </div>
    </section>

    <section class=\"card\">
      <h2>Order Latency by Hour</h2>
      <table id=\"latency\">
        <thead><tr><th>Hour (UTC)</th><th>Count</th><th>Avg (s)</th><th>p95 (s)</th><th>Max (s)</th></tr></thead>
        <tbody></tbody>
      </table>
    </section>
  </div>

  <script>
    const data = {payload};

    const fmtPct = (x) => `${{(Number(x || 0) * 100).toFixed(2)}}%`;

    document.getElementById('generated-at').textContent = data.generated_at || '';

    const fillBody = document.querySelector('#fill-rate tbody');
    (data.fill_rate_trend_7d || []).forEach((row) => {{
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${{row.date}}</td><td>${{row.submitted}}</td><td>${{row.filled}}</td><td>${{fmtPct(row.fill_rate)}}</td>`;
      fillBody.appendChild(tr);
    }});

    const rejectBody = document.querySelector('#reject-rate tbody');
    (data.reject_rate_by_symbol || []).forEach((row) => {{
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${{row.symbol}}</td><td>${{row.submitted}}</td><td>${{row.rejected}}</td><td>${{fmtPct(row.reject_rate)}}</td>`;
      rejectBody.appendChild(tr);
    }});

    const sl = data.slippage_distribution || {{}};
    document.getElementById('sl-count').textContent = String(sl.count || 0);
    document.getElementById('sl-p50').textContent = String(sl.p50 || 0);
    document.getElementById('sl-p95').textContent = String(sl.p95 || 0);
    document.getElementById('sl-max').textContent = String(sl.max || 0);

    const latencyBody = document.querySelector('#latency tbody');
    (data.order_latency_by_hour || []).forEach((row) => {{
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${{row.hour}}</td><td>${{row.count}}</td><td>${{row.avg_seconds}}</td><td>${{row.p95_seconds}}</td><td>${{row.max_seconds}}</td>`;
      latencyBody.appendChild(tr);
    }});
  </script>
</body>
</html>
"""


def export_execution_dashboard(
    db_path: str,
    output_path: str,
    *,
    refresh_seconds: int = 60,
) -> Dict[str, Any]:
    rows = _load_events(db_path)
    metrics = _compute_metrics(rows)

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_render_html(metrics, refresh_seconds), encoding="utf-8")

    return {
        "output_path": str(target),
        "metrics": metrics,
    }
