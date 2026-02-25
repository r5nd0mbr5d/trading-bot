"""Lightweight walk-forward experiment harness output utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Callable, Dict, List, Tuple

from research.models.artifacts import ModelArtifactMetadata, save_model_artifact


@dataclass
class ExperimentReport:
    experiment_id: str
    output_dir: Path
    aggregate_summary_path: Path
    promotion_check_path: Path
    fold_paths: List[Path]
    aggregate_summary: Dict[str, Any]
    promotion_check: Dict[str, Any]


@dataclass
class ModelTrainingReport:
    model_id: str
    model_dir: Path
    metadata: ModelArtifactMetadata
    metrics: Dict[str, float]
    model: Any


def _compute_aggregate_metrics(folds: List[Dict[str, Any]]) -> Dict[str, Any]:
    win_rates = [float(f.get("win_rate", 0.0) or 0.0) for f in folds]
    profit_factors = [float(f.get("profit_factor", 0.0) or 0.0) for f in folds]
    fill_rates = [float(f.get("fill_rate", 0.0) or 0.0) for f in folds]
    pr_aucs = [
        float(f.get("pr_auc", f.get("metrics", {}).get("val_pr_auc", 0.0)) or 0.0)
        for f in folds
    ]
    roc_aucs = [
        float(f.get("roc_auc", f.get("metrics", {}).get("val_roc_auc", 0.0)) or 0.0)
        for f in folds
    ]
    annualized_returns = [
        float(f.get("annualized_return_pct", f.get("metrics", {}).get("annualized_return_pct", 0.0)) or 0.0)
        for f in folds
    ]

    passed_folds = sum(1 for f in folds if bool(f.get("passed", False)))
    total_folds = len(folds)

    return {
        "fold_count": total_folds,
        "passed_folds": passed_folds,
        "pass_rate": (passed_folds / total_folds) if total_folds else 0.0,
        "mean_win_rate": mean(win_rates) if win_rates else 0.0,
        "mean_profit_factor": mean(profit_factors) if profit_factors else 0.0,
        "mean_fill_rate": mean(fill_rates) if fill_rates else 0.0,
        "mean_pr_auc": mean(pr_aucs) if pr_aucs else 0.0,
        "mean_roc_auc": mean(roc_aucs) if roc_aucs else 0.0,
        "mean_annualized_return_pct": mean(annualized_returns) if annualized_returns else 0.0,
    }


def _extract_claim_integrity(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and evaluate claim-integrity evidence from metadata.

    Parameters
    ----------
    metadata : Dict[str, Any]
        Experiment metadata payload.

    Returns
    -------
    Dict[str, Any]
        Claim-integrity fields with completeness metadata.
    """
    evidence = metadata.get("claim_integrity", {}) if isinstance(metadata, dict) else {}
    if not isinstance(evidence, dict):
        evidence = {}

    fields = {
        "out_of_sample_period": evidence.get("out_of_sample_period"),
        "transaction_costs_slippage_assumptions": evidence.get(
            "transaction_costs_slippage_assumptions"
        ),
        "max_drawdown": evidence.get("max_drawdown"),
        "turnover": evidence.get("turnover"),
        "tested_variants": evidence.get("tested_variants"),
    }

    missing_fields = [
        name
        for name, value in fields.items()
        if value is None or (isinstance(value, str) and not value.strip())
    ]

    return {
        **fields,
        "missing_fields": missing_fields,
        "is_complete": len(missing_fields) == 0,
    }


def run_experiment(
    experiment_id: str,
    fold_results: List[Dict[str, Any]],
    output_dir: str,
    metadata: Dict[str, Any],
) -> ExperimentReport:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    fold_paths: List[Path] = []
    normalized_folds: List[Dict[str, Any]] = []

    for idx, fold in enumerate(fold_results, start=1):
        fold_payload = {
            "experiment_id": experiment_id,
            "fold_id": f"F{idx}",
            **fold,
        }
        fold_path = root / f"fold_F{idx}.json"
        fold_path.write_text(json.dumps(fold_payload, indent=2), encoding="utf-8")
        fold_paths.append(fold_path)
        normalized_folds.append(fold_payload)

    aggregate_metrics = _compute_aggregate_metrics(normalized_folds)
    aggregate_summary = {
        "experiment_id": experiment_id,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
        "folds": normalized_folds,
        "aggregate_metrics": aggregate_metrics,
    }

    hypothesis = metadata.get("hypothesis", {}) if isinstance(metadata, dict) else {}
    n_prior_tests = int(hypothesis.get("n_prior_tests", 0) or 0)
    adjusted_alpha = float(hypothesis.get("adjusted_alpha", 0.05 / (n_prior_tests + 1)))
    registered_before_test = bool(hypothesis.get("registered_before_test", True))

    promotion_eligible = (
        aggregate_metrics["pass_rate"] >= 0.75
        and aggregate_metrics["mean_win_rate"] >= 0.50
        and aggregate_metrics["mean_profit_factor"] >= 1.10
    )

    claim_integrity = _extract_claim_integrity(metadata)
    caution_flags: list[str] = []
    if not claim_integrity["is_complete"]:
        caution_flags.append("claim_integrity_fields_missing")

    if (
        aggregate_metrics["mean_annualized_return_pct"] > 100.0
        and not claim_integrity["is_complete"]
    ):
        caution_flags.append("high_return_claim_unverified")

    promotion_check = {
        "experiment_id": experiment_id,
        "evaluated_at": aggregate_summary["evaluated_at"],
        "promotion_eligible": promotion_eligible,
        "n_prior_tests": n_prior_tests,
        "adjusted_alpha": adjusted_alpha,
        "registered_before_test": registered_before_test,
        "claim_integrity": claim_integrity,
        "caution_flags": caution_flags,
        "gates": [
            {
                "gate": "fold_pass_rate",
                "threshold": 0.75,
                "actual": aggregate_metrics["pass_rate"],
                "passed": aggregate_metrics["pass_rate"] >= 0.75,
            },
            {
                "gate": "mean_win_rate",
                "threshold": 0.50,
                "actual": aggregate_metrics["mean_win_rate"],
                "passed": aggregate_metrics["mean_win_rate"] >= 0.50,
            },
            {
                "gate": "mean_profit_factor",
                "threshold": 1.10,
                "actual": aggregate_metrics["mean_profit_factor"],
                "passed": aggregate_metrics["mean_profit_factor"] >= 1.10,
            },
            {
                "gate": "mean_pr_auc",
                "threshold": 0.55,
                "actual": aggregate_metrics["mean_pr_auc"],
                "passed": aggregate_metrics["mean_pr_auc"] >= 0.55,
            },
        ],
    }
    if not registered_before_test:
        promotion_check["caution"] = "CAUTION: hypothesis not pre-registered"
    if caution_flags:
        promotion_check["claim_integrity_caution"] = (
            "CAUTION: claim-integrity evidence incomplete; review required before promotion discussion"
        )

    aggregate_summary_path = root / "aggregate_summary.json"
    promotion_check_path = root / "promotion_check.json"
    aggregate_summary_path.write_text(json.dumps(aggregate_summary, indent=2), encoding="utf-8")
    promotion_check_path.write_text(json.dumps(promotion_check, indent=2), encoding="utf-8")

    return ExperimentReport(
        experiment_id=experiment_id,
        output_dir=root,
        aggregate_summary_path=aggregate_summary_path,
        promotion_check_path=promotion_check_path,
        fold_paths=fold_paths,
        aggregate_summary=aggregate_summary,
        promotion_check=promotion_check,
    )


def train_and_save_model(
    *,
    model_id: str,
    trainer: Callable[..., Tuple[Any, Dict[str, float]]],
    trainer_kwargs: Dict[str, Any],
    metadata: Dict[str, Any],
    artifacts_root: str = "research/models/artifacts",
) -> ModelTrainingReport:
    model, metrics = trainer(**trainer_kwargs)

    artifact_metadata = ModelArtifactMetadata(
        model_id=model_id,
        model_type=str(metadata["model_type"]),
        snapshot_id=str(metadata["snapshot_id"]),
        feature_version=str(metadata["feature_version"]),
        label_version=str(metadata["label_version"]),
        train_window=str(metadata["train_window"]),
        val_window=str(metadata["val_window"]),
        metrics={str(k): float(v) for k, v in metrics.items()},
        artifact_hash="",
        created_at_utc=str(metadata.get("created_at_utc") or datetime.now(timezone.utc).isoformat()),
        model_file=str(metadata.get("model_file") or "model.bin"),
        extra_metadata=metadata.get("extra_metadata"),
    )

    model_dir, stored_metadata = save_model_artifact(
        model,
        artifact_metadata,
        artifacts_root=artifacts_root,
    )

    return ModelTrainingReport(
        model_id=model_id,
        model_dir=model_dir,
        metadata=stored_metadata,
        metrics=metrics,
        model=model,
    )
