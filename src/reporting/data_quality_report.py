"""Data quality summary report export for market bars."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.reporting.engine import ReportingEngine


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


def _load_market_bars(db_path: str) -> List[sqlite3.Row]:
    return ReportingEngine(db_path).fetch_market_bars()


def _compute_report(
    rows: List[sqlite3.Row],
    *,
    now_utc: datetime,
    max_staleness_seconds: int,
    expected_gap_seconds: int,
) -> Dict[str, Any]:
    by_symbol: Dict[str, list[tuple[datetime, float, float, float, float]]] = {}
    for row in rows:
        symbol = str(row["symbol"] or "").strip()
        ts = _parse_ts(str(row["timestamp"] or ""))
        if not symbol or ts is None:
            continue
        by_symbol.setdefault(symbol, []).append(
            (
                ts,
                float(row["open"]),
                float(row["high"]),
                float(row["low"]),
                float(row["close"]),
            )
        )

    symbol_reports: list[dict[str, Any]] = []
    for symbol, samples in sorted(by_symbol.items()):
        samples.sort(key=lambda item: item[0])
        timestamps = [sample[0] for sample in samples]

        last_ts = timestamps[-1]
        staleness_seconds = max((now_utc - last_ts).total_seconds(), 0.0)
        stale = staleness_seconds > float(max_staleness_seconds)

        gap_count = 0
        if len(timestamps) > 1:
            for prev_ts, curr_ts in zip(timestamps[:-1], timestamps[1:]):
                gap = (curr_ts - prev_ts).total_seconds()
                if gap > float(expected_gap_seconds):
                    gap_count += 1

        ohlc_violations = 0
        for _, open_, high, low, close in samples:
            if high < max(open_, close, low) or low > min(open_, close, high):
                ohlc_violations += 1

        symbol_reports.append(
            {
                "symbol": symbol,
                "bar_count": len(samples),
                "latest_timestamp": last_ts.isoformat(),
                "staleness_seconds": round(staleness_seconds, 3),
                "stale": stale,
                "gap_count": gap_count,
                "ohlc_violation_count": ohlc_violations,
            }
        )

    return {
        "generated_at": now_utc.isoformat(),
        "symbols_checked": len(symbol_reports),
        "max_staleness_seconds": int(max_staleness_seconds),
        "expected_gap_seconds": int(expected_gap_seconds),
        "symbols": symbol_reports,
    }


def _append_dashboard_section(dashboard_path: Path, report: Dict[str, Any]) -> None:
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)

    section = [
        '<section class="card">',
        "  <h2>Data Quality Summary</h2>",
        "  <table>",
        "    <thead><tr><th>Symbol</th><th>Bars</th><th>Stale</th><th>Gap Count</th><th>OHLC Violations</th></tr></thead>",
        "    <tbody>",
    ]
    for row in report.get("symbols", []):
        section.append(
            "    <tr>"
            f"<td>{row['symbol']}</td>"
            f"<td>{row['bar_count']}</td>"
            f"<td>{'yes' if row['stale'] else 'no'}</td>"
            f"<td>{row['gap_count']}</td>"
            f"<td>{row['ohlc_violation_count']}</td>"
            "</tr>"
        )
    section.extend(["    </tbody>", "  </table>", "</section>"])
    section_html = "\n".join(section)

    if dashboard_path.exists():
        html = dashboard_path.read_text(encoding="utf-8")
        marker = "<!-- DATA_QUALITY_SUMMARY -->"
        if marker in html:
            before, _, after = html.partition(marker)
            if "<!-- /DATA_QUALITY_SUMMARY -->" in after:
                _, _, trailing = after.partition("<!-- /DATA_QUALITY_SUMMARY -->")
            else:
                trailing = after
            updated = (
                before
                + marker
                + "\n"
                + section_html
                + "\n<!-- /DATA_QUALITY_SUMMARY -->"
                + trailing
            )
        elif "</body>" in html:
            updated = html.replace(
                "</body>",
                f"<!-- DATA_QUALITY_SUMMARY -->\n{section_html}\n<!-- /DATA_QUALITY_SUMMARY -->\n</body>",
            )
        else:
            updated = (
                html
                + "\n<!-- DATA_QUALITY_SUMMARY -->\n"
                + section_html
                + "\n<!-- /DATA_QUALITY_SUMMARY -->\n"
            )
    else:
        updated = (
            "<!doctype html><html><body>\n"
            "<h1>Execution Dashboard</h1>\n"
            "<!-- DATA_QUALITY_SUMMARY -->\n" + section_html + "\n<!-- /DATA_QUALITY_SUMMARY -->\n"
            "</body></html>\n"
        )

    dashboard_path.write_text(updated, encoding="utf-8")


def export_data_quality_report(
    db_path: str,
    output_path: str,
    *,
    dashboard_path: str = "reports/execution_dashboard.html",
    max_staleness_seconds: int = 3600,
    expected_gap_seconds: int = 3600,
    now_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    now = now_utc or datetime.now(timezone.utc)
    rows = _load_market_bars(db_path)
    report = _compute_report(
        rows,
        now_utc=now,
        max_staleness_seconds=max_staleness_seconds,
        expected_gap_seconds=expected_gap_seconds,
    )

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")

    _append_dashboard_section(Path(dashboard_path), report)

    return {
        "output_path": str(target),
        "dashboard_path": str(Path(dashboard_path)),
        "report": report,
    }
