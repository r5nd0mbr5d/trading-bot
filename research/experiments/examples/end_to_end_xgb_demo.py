"""End-to-end demo: snapshot -> config -> XGBoost pipeline.

Defaults to a stub trainer so it runs without ML dependencies.
Use --use-real-trainer to run the actual XGBoost trainer.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd

from research.data.snapshots import save_snapshot
from research.experiments.config import ExperimentConfig
from research.experiments.xgboost_pipeline import run_xgboost_experiment
from research.models.train_xgboost import train_xgboost_model


def _sample_bars(rows: int = 260) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=rows, freq="D", tz="UTC")
    base = np.arange(rows, dtype=float)
    oscillation = np.sin(base / 5.0) * 0.5
    close = pd.Series(np.round(100 + base * 0.1 + oscillation, 4), index=index)
    return pd.DataFrame(
        {
            "open": (close * 0.99).round(4),
            "high": (close * 1.01).round(4),
            "low": (close * 0.98).round(4),
            "close": close.round(4),
            "volume": 1000,
        },
        index=index,
    )


def _stub_trainer(**kwargs: Any) -> Tuple[Any, Dict[str, float]]:
    _ = kwargs
    return {"weights": [1, 2, 3]}, {"val_accuracy": 0.55, "val_pos_rate": 0.4}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run end-to-end XGBoost demo pipeline")
    parser.add_argument("--output-root", default="research/experiments/demo_xgb")
    parser.add_argument("--snapshot-root", default="research/data/snapshots")
    parser.add_argument("--use-real-trainer", action="store_true")
    args = parser.parse_args()

    output_root = Path(args.output_root)
    snapshot_root = Path(args.snapshot_root)
    snapshot_root.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)

    snapshot_id = f"demo_xgb_{datetime.now().strftime('%Y%m%d')}"
    snapshot_dir = snapshot_root / snapshot_id

    save_snapshot(
        _sample_bars(),
        output_dir=str(snapshot_root),
        config={"symbol": "DEMO"},
        snapshot_id=snapshot_id,
    )

    config = ExperimentConfig(
        snapshot_dir=str(snapshot_dir),
        experiment_id=snapshot_id,
        symbol="DEMO",
        output_dir=str(output_root / snapshot_id),
        horizon_days=5,
        train_ratio=0.6,
        val_ratio=0.2,
        gap_days=0,
        feature_version="v1",
        label_version="h5",
        model_id=f"{snapshot_id}_xgb",
        xgb_params={"max_depth": 4, "n_estimators": 300},
        calibrate=False,
    )

    config_path = output_root / f"{snapshot_id}_config.json"
    config_path.write_text(json.dumps(config.__dict__, indent=2), encoding="utf-8")

    trainer = train_xgboost_model if args.use_real_trainer else _stub_trainer

    result = run_xgboost_experiment(
        snapshot_dir=config.snapshot_dir,
        experiment_id=config.experiment_id,
        symbol=config.symbol,
        output_dir=config.output_dir,
        horizon_days=config.horizon_days,
        train_ratio=config.train_ratio,
        val_ratio=config.val_ratio,
        gap_days=config.gap_days,
        feature_version=config.feature_version,
        label_version=config.label_version,
        model_id=config.model_id,
        model_params=config.xgb_params,
        calibrate=config.calibrate,
        trainer=trainer,
    )

    print(f"Experiment outputs: {result.output_dir}")
    print(f"Training report: {result.training_report_path}")
    print(f"Config: {config_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
