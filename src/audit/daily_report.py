"""Daily end-of-session paper-trading report generation."""

from __future__ import annotations

import json
import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from src.reporting.engine import ReportingEngine


class DailyReportGenerator:
    """Generate a daily P&L summary from audit events."""

    def __init__(self, db_path: str):
        self._engine = ReportingEngine(db_path)
        self._db_path = db_path

    @staticmethod
    def _parse_timestamp(value: str | None) -> datetime | None:
        if not value:
            return None
        raw = value.strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def _safe_payload(payload_json: str | None) -> dict[str, Any]:
        if not payload_json:
            return {}
        try:
            parsed = json.loads(payload_json)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _detect_pnl(payload: dict[str, Any]) -> float:
        for key in ("realized_pnl", "pnl", "profit_loss", "mark_to_close_pnl"):
            value = payload.get(key)
            if isinstance(value, (int, float)):
                return float(value)
        return 0.0

    def build_report(self, report_date: str | None = None) -> dict[str, Any]:
        target_date = report_date or datetime.now(timezone.utc).date().isoformat()
        events = self._engine.fetch_audit_events()

        fills = 0
        pnl_proxy = 0.0
        guardrail_firings = 0
        sharpe_running: float | None = None
        max_intraday_drawdown: float | None = None
        open_positions = 0

        for row in events:
            ts = self._parse_timestamp(str(row["timestamp"]))
            if ts is None or ts.date().isoformat() != target_date:
                continue

            event_type = str(row["event_type"] or "")
            payload = self._safe_payload(row["payload_json"])

            if event_type in {"FILL", "ORDER_FILLED", "TRADE"}:
                fills += 1
                pnl_proxy += self._detect_pnl(payload)

            if "GUARDRAIL" in event_type or "CIRCUIT_BREAKER" in event_type or event_type == "KILL_SWITCH":
                guardrail_firings += 1

            if isinstance(payload.get("sharpe"), (int, float)):
                sharpe_running = float(payload["sharpe"])

            drawdown = payload.get("drawdown")
            if isinstance(drawdown, (int, float)):
                drawdown_value = float(drawdown)
                if max_intraday_drawdown is None or drawdown_value > max_intraday_drawdown:
                    max_intraday_drawdown = drawdown_value

            positions = payload.get("positions")
            if isinstance(positions, list):
                open_positions = len(positions)

        return {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "report_date": target_date,
            "db_path": self._db_path,
            "fills": fills,
            "pnl_proxy_mark_to_close": round(pnl_proxy, 6),
            "open_positions": open_positions,
            "sharpe_running": sharpe_running,
            "max_intraday_drawdown": max_intraday_drawdown,
            "guardrail_firings": guardrail_firings,
        }

    def write_report(self, report: dict[str, Any], output_dir: str = "reports/daily") -> str:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / f"{report['report_date']}.json"
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return str(output_path)

    @staticmethod
    def send_email(report: dict[str, Any], to_email: str) -> None:
        smtp_host = os.getenv("SMTP_HOST", "localhost")
        smtp_port = int(os.getenv("SMTP_PORT", "25"))
        from_email = os.getenv("SMTP_FROM", "trading-bot@localhost")

        body = (
            f"Daily report for {report['report_date']}\n"
            f"fills: {report['fills']}\n"
            f"pnl_proxy_mark_to_close: {report['pnl_proxy_mark_to_close']}\n"
            f"open_positions: {report['open_positions']}\n"
            f"sharpe_running: {report['sharpe_running']}\n"
            f"max_intraday_drawdown: {report['max_intraday_drawdown']}\n"
            f"guardrail_firings: {report['guardrail_firings']}\n"
        )

        message = EmailMessage()
        message["Subject"] = f"Trading Bot Daily Report {report['report_date']}"
        message["From"] = from_email
        message["To"] = to_email
        message.set_content(body)

        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
            smtp.send_message(message)
