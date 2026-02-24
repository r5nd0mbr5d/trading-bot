"""Paper session reconciliation report with tolerance-based drift flags."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, Optional

from src.audit.session_summary import summarize_paper_session

_DEFAULT_TOLERANCES = {
    "fill_rate": 0.05,
    "win_rate": 0.08,
    "profit_factor": 0.20,
    "avg_slippage_pct": 0.0010,
    "avg_fee_per_trade": 0.25,
    "realized_pnl": 250.0,
}


def _to_float(value: Any) -> float:
    if isinstance(value, str) and value.lower() == "inf":
        return float("inf")
    return float(value)


def build_reconciliation_report(
    actual_metrics: Dict[str, Any],
    expected_metrics: Dict[str, Any],
    tolerances: Optional[Dict[str, float]] = None,
) -> dict:
    """Compare expected vs actual metrics and flag drift by tolerance."""
    tol = dict(_DEFAULT_TOLERANCES)
    if tolerances:
        tol.update(tolerances)

    metric_rows = []
    drift_flag_count = 0
    for metric, expected_value in expected_metrics.items():
        if metric not in actual_metrics:
            metric_rows.append(
                {
                    "metric": metric,
                    "expected": expected_value,
                    "actual": None,
                    "drift_abs": None,
                    "tolerance": tol.get(metric),
                    "within_tolerance": False,
                    "drift_flag": True,
                    "note": "metric missing from actual summary",
                }
            )
            drift_flag_count += 1
            continue

        actual_value = actual_metrics[metric]
        try:
            expected_num = _to_float(expected_value)
            actual_num = _to_float(actual_value)
        except (TypeError, ValueError):
            values_match = actual_value == expected_value
            metric_rows.append(
                {
                    "metric": metric,
                    "expected": expected_value,
                    "actual": actual_value,
                    "drift_abs": None,
                    "tolerance": tol.get(metric),
                    "within_tolerance": values_match,
                    "drift_flag": not values_match,
                    "note": "non-numeric metric mismatch" if not values_match else "",
                }
            )
            if not values_match:
                drift_flag_count += 1
            continue

        drift_abs = abs(actual_num - expected_num)
        tolerance = float(tol.get(metric, 0.0))
        within_tolerance = drift_abs <= tolerance
        drift_flag = not within_tolerance
        if drift_flag:
            drift_flag_count += 1

        metric_rows.append(
            {
                "metric": metric,
                "expected": expected_value,
                "actual": actual_value,
                "drift_abs": round(drift_abs, 8),
                "tolerance": tolerance,
                "within_tolerance": within_tolerance,
                "drift_flag": drift_flag,
                "note": "",
            }
        )

    return {
        "ok": drift_flag_count == 0,
        "drift_flag_count": drift_flag_count,
        "metric_count": len(metric_rows),
        "rows": metric_rows,
        "tolerances": tol,
    }


def export_paper_reconciliation(
    db_path: str,
    output_dir: str,
    expected_metrics: Dict[str, Any],
    *,
    base_currency: str = "GBP",
    fx_rates: Optional[Dict[str, float]] = None,
    fx_rate_timestamps: Optional[Dict[str, str]] = None,
    fx_rate_max_age_hours: Optional[float] = None,
    tolerances: Optional[Dict[str, float]] = None,
) -> dict:
    """Summarize a paper session and export reconciliation report."""
    actual = summarize_paper_session(
        db_path,
        base_currency=base_currency,
        fx_rates=fx_rates,
        fx_rate_timestamps=fx_rate_timestamps,
        fx_rate_max_age_hours=fx_rate_max_age_hours,
    )
    report = build_reconciliation_report(actual, expected_metrics, tolerances)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "paper_reconciliation.json"
    csv_path = out / "paper_reconciliation.csv"

    payload = {
        "db_path": db_path,
        "base_currency": base_currency,
        "actual_summary": actual,
        "expected_metrics": expected_metrics,
        "report": report,
    }

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "metric",
                "expected",
                "actual",
                "drift_abs",
                "tolerance",
                "within_tolerance",
                "drift_flag",
                "note",
            ]
        )
        for row in report["rows"]:
            writer.writerow(
                [
                    row["metric"],
                    row["expected"],
                    row["actual"],
                    row["drift_abs"],
                    row["tolerance"],
                    row["within_tolerance"],
                    row["drift_flag"],
                    row["note"],
                ]
            )

    return {
        "json_path": str(json_path),
        "csv_path": str(csv_path),
        "report": report,
    }
