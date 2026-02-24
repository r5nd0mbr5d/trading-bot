"""Execution drift monitoring for rolling session summaries."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class ExecutionSnapshot:
    session_ts: str
    fill_rate: float
    avg_slippage_pct: float


class ExecutionTrendMonitor:
    """Detect monotonic execution degradation over recent sessions."""

    def __init__(
        self,
        window: int = 5,
        fill_rate_decline_threshold: float = 0.05,
        slippage_rise_threshold: float = 0.001,
    ):
        self.window = window
        self.fill_rate_decline_threshold = fill_rate_decline_threshold
        self.slippage_rise_threshold = slippage_rise_threshold
        self._snapshots: List[ExecutionSnapshot] = []

    def record_session(self, snapshot: ExecutionSnapshot) -> List[str]:
        self._snapshots.append(snapshot)
        if len(self._snapshots) > self.window:
            self._snapshots.pop(0)
        return self._check_trends()

    def _check_trends(self) -> List[str]:
        warnings: List[str] = []
        if len(self._snapshots) < 3:
            return warnings

        fill_rates = [s.fill_rate for s in self._snapshots]
        slippages = [s.avg_slippage_pct for s in self._snapshots]

        if all(fill_rates[i] >= fill_rates[i + 1] for i in range(len(fill_rates) - 1)):
            total_decline = fill_rates[0] - fill_rates[-1]
            if total_decline >= self.fill_rate_decline_threshold:
                warnings.append(
                    f"fill_rate declining {len(fill_rates)} sessions: {fill_rates[0]:.3f} -> {fill_rates[-1]:.3f}"
                )

        if all(slippages[i] <= slippages[i + 1] for i in range(len(slippages) - 1)):
            total_rise = slippages[-1] - slippages[0]
            if total_rise >= self.slippage_rise_threshold:
                warnings.append(
                    f"avg_slippage rising {len(slippages)} sessions: {slippages[0]:.4f} -> {slippages[-1]:.4f}"
                )

        return warnings


def update_execution_trend(
    summary: Dict[str, Any],
    trend_path: str,
    *,
    window: int = 5,
    fill_rate_decline_threshold: float = 0.05,
    slippage_rise_threshold: float = 0.001,
) -> Dict[str, Any]:
    """Append a session summary to the trend log and return warnings."""
    now = datetime.now(timezone.utc).isoformat()
    snapshot = ExecutionSnapshot(
        session_ts=summary.get("last_event_ts") or now,
        fill_rate=float(summary.get("fill_rate", 0.0) or 0.0),
        avg_slippage_pct=float(summary.get("avg_slippage_pct", 0.0) or 0.0),
    )

    trend_file = Path(trend_path)
    history: List[Dict[str, Any]] = []
    if trend_file.exists():
        try:
            payload = json.loads(trend_file.read_text(encoding="utf-8"))
            history = payload.get("history", []) if isinstance(payload, dict) else []
        except json.JSONDecodeError:
            history = []

    history.append(
        {
            "session_ts": snapshot.session_ts,
            "fill_rate": snapshot.fill_rate,
            "avg_slippage_pct": snapshot.avg_slippage_pct,
        }
    )

    monitor = ExecutionTrendMonitor(
        window=window,
        fill_rate_decline_threshold=fill_rate_decline_threshold,
        slippage_rise_threshold=slippage_rise_threshold,
    )
    for item in history[-window:]:
        monitor.record_session(
            ExecutionSnapshot(
                session_ts=item.get("session_ts", ""),
                fill_rate=float(item.get("fill_rate", 0.0) or 0.0),
                avg_slippage_pct=float(item.get("avg_slippage_pct", 0.0) or 0.0),
            )
        )
    warnings = monitor._check_trends()

    trend_payload = {
        "generated_at": now,
        "history": history[-window:],
        "warnings": warnings,
    }
    trend_file.parent.mkdir(parents=True, exist_ok=True)
    trend_file.write_text(json.dumps(trend_payload, indent=2), encoding="utf-8")

    return {
        "trend_path": str(trend_file),
        "warnings": warnings,
        "history": trend_payload["history"],
    }
