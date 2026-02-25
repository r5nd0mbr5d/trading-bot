"""Experiment configuration loader."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import json


@dataclass
class ExperimentConfig:
    snapshot_dir: str
    experiment_id: str
    symbol: str
    output_dir: str
    horizon_days: int = 5
    train_ratio: float = 0.6
    val_ratio: float = 0.2
    gap_days: int = 0
    feature_version: str = "v1"
    label_version: str = "h5"
    model_id: Optional[str] = None
    xgb_params: Optional[Dict[str, Any]] = None
    xgb_preset: Optional[str] = None
    calibrate: bool = False
    label_type: str = "direction"
    threshold_bps: float = 45.0
    hypothesis: Optional[Dict[str, Any]] = None
    walk_forward: bool = False
    train_months: int = 6
    val_months: int = 3
    test_months: int = 3
    step_months: int = 3


_REQUIRED_FIELDS = {"snapshot_dir", "experiment_id", "symbol", "output_dir"}
_OPTIONAL_FIELDS = {
    "horizon_days",
    "train_ratio",
    "val_ratio",
    "gap_days",
    "feature_version",
    "label_version",
    "model_id",
    "xgb_params",
    "xgb_preset",
    "calibrate",
    "label_type",
    "threshold_bps",
    "hypothesis",
    "walk_forward",
    "train_months",
    "val_months",
    "test_months",
    "step_months",
}
_ALLOWED_FIELDS = _REQUIRED_FIELDS | _OPTIONAL_FIELDS


def load_experiment_config(path: str | Path) -> ExperimentConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Experiment config not found: {config_path}")

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    unknown = set(payload.keys()) - _ALLOWED_FIELDS
    if unknown:
        raise ValueError(f"Unknown config fields: {', '.join(sorted(unknown))}")
    missing = _REQUIRED_FIELDS - set(payload.keys())
    if missing:
        raise ValueError(f"Missing required config fields: {', '.join(sorted(missing))}")

    if not isinstance(payload.get("snapshot_dir"), str):
        raise ValueError("snapshot_dir must be a string")
    if not isinstance(payload.get("experiment_id"), str):
        raise ValueError("experiment_id must be a string")
    if not isinstance(payload.get("symbol"), str):
        raise ValueError("symbol must be a string")
    if not isinstance(payload.get("output_dir"), str):
        raise ValueError("output_dir must be a string")
    if "xgb_params" in payload and payload["xgb_params"] is not None:
        if not isinstance(payload["xgb_params"], dict):
            raise ValueError("xgb_params must be an object")
    if "xgb_preset" in payload and payload["xgb_preset"] is not None:
        if not isinstance(payload["xgb_preset"], str):
            raise ValueError("xgb_preset must be a string")
    if "label_type" in payload and payload["label_type"] is not None:
        label_type = str(payload["label_type"]).strip().lower()
        if label_type not in {"direction", "threshold"}:
            raise ValueError("label_type must be 'direction' or 'threshold'")
    if "threshold_bps" in payload and payload["threshold_bps"] is not None:
        _ = float(payload["threshold_bps"])
    if "hypothesis" in payload and payload["hypothesis"] is not None:
        hypothesis = payload["hypothesis"]
        if not isinstance(hypothesis, dict):
            raise ValueError("hypothesis must be an object")
        required_hypothesis_fields = {
            "hypothesis_id",
            "hypothesis_text",
            "n_prior_tests",
            "registered_before_test",
        }
        missing_hypothesis = required_hypothesis_fields - set(hypothesis.keys())
        if missing_hypothesis:
            missing = ", ".join(sorted(missing_hypothesis))
            raise ValueError(f"Missing required hypothesis fields: {missing}")

    horizon_days = int(payload.get("horizon_days", 5))
    if horizon_days <= 0:
        raise ValueError("horizon_days must be positive")

    train_ratio = float(payload.get("train_ratio", 0.6))
    val_ratio = float(payload.get("val_ratio", 0.2))
    if not (0.0 < train_ratio < 1.0):
        raise ValueError("train_ratio must be between 0 and 1")
    if not (0.0 < val_ratio < 1.0):
        raise ValueError("val_ratio must be between 0 and 1")
    if train_ratio + val_ratio >= 1.0:
        raise ValueError("train_ratio + val_ratio must be < 1.0")

    gap_days = int(payload.get("gap_days", 0))
    if gap_days < 0:
        raise ValueError("gap_days must be >= 0")

    train_months = int(payload.get("train_months", 6))
    val_months = int(payload.get("val_months", 3))
    test_months = int(payload.get("test_months", 3))
    step_months = int(payload.get("step_months", 3))
    if train_months <= 0 or val_months <= 0 or test_months <= 0 or step_months <= 0:
        raise ValueError("train_months, val_months, test_months and step_months must be > 0")

    return ExperimentConfig(
        snapshot_dir=str(payload["snapshot_dir"]),
        experiment_id=str(payload["experiment_id"]),
        symbol=str(payload["symbol"]),
        output_dir=str(payload["output_dir"]),
        horizon_days=int(payload.get("horizon_days", 5)),
        train_ratio=float(payload.get("train_ratio", 0.6)),
        val_ratio=float(payload.get("val_ratio", 0.2)),
        gap_days=int(payload.get("gap_days", 0)),
        feature_version=str(payload.get("feature_version", "v1")),
        label_version=str(payload.get("label_version", "h5")),
        model_id=payload.get("model_id"),
        xgb_params=payload.get("xgb_params"),
        xgb_preset=payload.get("xgb_preset"),
        calibrate=bool(payload.get("calibrate", False)),
        label_type=str(payload.get("label_type", "direction")),
        threshold_bps=float(payload.get("threshold_bps", 45.0)),
        hypothesis=payload.get("hypothesis"),
        walk_forward=bool(payload.get("walk_forward", False)),
        train_months=train_months,
        val_months=val_months,
        test_months=test_months,
        step_months=step_months,
    )
