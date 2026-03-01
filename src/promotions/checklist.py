"""Promotion checklist generation for paper-readiness workflows."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _load_summary(summary_json_path: Optional[str]) -> Optional[Dict[str, Any]]:
    if not summary_json_path:
        return None
    path = Path(summary_json_path)
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        payload = json.load(f)
    if isinstance(payload, dict):
        return payload
    return None


def load_promotion_checklist(checklist_path: str) -> Dict[str, Any]:
    path = Path(checklist_path)
    if not path.exists():
        raise ValueError(f"Promotion checklist not found: {path}")
    with path.open(encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("Promotion checklist must be a JSON object")
    return payload


def validate_promotion_checklist(checklist: Dict[str, Any], strategy: str) -> List[str]:
    errors: List[str] = []
    if checklist.get("checklist_version") != "1.0.0":
        errors.append("checklist_version must be 1.0.0")
    if checklist.get("strategy") != strategy:
        errors.append(f"strategy mismatch: {checklist.get('strategy')} != {strategy}")
    if checklist.get("decision") != "READY":
        errors.append(f"decision must be READY (got {checklist.get('decision')})")
    if checklist.get("overall_ready") is not True:
        errors.append("overall_ready must be true")
    failures = checklist.get("paper_readiness_failures") or []
    if failures:
        errors.append("paper_readiness_failures must be empty")
    return errors


def build_promotion_checklist(
    strategy: str,
    *,
    summary: Optional[Dict[str, Any]] = None,
    summary_json_path: Optional[str] = None,
    base_currency: str = "GBP",
) -> Dict[str, Any]:
    from src.strategies.registry import paper_readiness_failures

    paper_summary = summary or _load_summary(summary_json_path)
    failures = paper_readiness_failures(paper_summary or {}) if paper_summary else []

    paper_metrics_status = "pending"
    if paper_summary is not None:
        paper_metrics_status = "pass" if not failures else "fail"

    checklist = {
        "checklist_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy": strategy,
        "base_currency": base_currency,
        "summary_json_path": summary_json_path,
        "pre_paper_checks": [
            {
                "id": "tests_all_pass",
                "label": "All test suites pass",
                "required": True,
                "status": "pending",
                "evidence": "Run python -m pytest tests/ -v",
            },
            {
                "id": "backtest_review",
                "label": "Backtest and walk-forward reviewed",
                "required": True,
                "status": "pending",
                "evidence": "Attach latest backtest + walk-forward report",
            },
        ],
        "in_paper_checks": [
            {
                "id": "health_check_green",
                "label": "UK health check passes with no blocking errors",
                "required": True,
                "status": "pending",
                "evidence": "python main.py uk_health_check --profile uk_paper --strict-health",
            },
            {
                "id": "reconciliation_below_5pct",
                "label": "Reconciliation drift remains below 5%",
                "required": True,
                "status": "pending",
                "evidence": "paper_reconcile output",
            },
            {
                "id": "paper_readiness_metrics",
                "label": "Paper readiness threshold checks",
                "required": True,
                "status": paper_metrics_status,
                "evidence": failures if failures else "paper_readiness_failures() clean",
            },
        ],
        "exit_criteria": [
            {
                "id": "manual_review_signoff",
                "label": "Manual review and sign-off recorded",
                "required": True,
                "status": "pending",
                "evidence": "decision rubric JSON in reports/promotions/",
            }
        ],
        "paper_readiness_failures": failures,
    }

    all_required = [
        *checklist["pre_paper_checks"],
        *checklist["in_paper_checks"],
        *checklist["exit_criteria"],
    ]
    overall_ready = all(
        item.get("status") == "pass" for item in all_required if item.get("required")
    )
    checklist["overall_ready"] = overall_ready
    checklist["decision"] = "READY" if overall_ready else "NOT_READY"

    return checklist


def export_promotion_checklist(
    output_dir: str,
    strategy: str,
    *,
    summary_json_path: Optional[str] = None,
    base_currency: str = "GBP",
) -> Dict[str, str]:
    checklist = build_promotion_checklist(
        strategy,
        summary_json_path=summary_json_path,
        base_currency=base_currency,
    )

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    output_path = out / "promotion_checklist.json"

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(checklist, f, indent=2)

    return {
        "output_path": str(output_path),
        "decision": checklist["decision"],
    }
