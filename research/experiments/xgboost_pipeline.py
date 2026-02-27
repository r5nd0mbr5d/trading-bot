"""XGBoost experiment pipeline for research datasets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

import json

import numpy as np
import pandas as pd

from research.data.features import build_drop_manifest, compute_features, drop_nan_rows
from research.data.labels import compute_labels, compute_thresholds
from research.data.snapshots import load_snapshot
from research.data.splits import apply_gap, apply_scaler, build_walk_forward_folds, fit_scaler
from research.experiments.harness import ExperimentReport, ModelTrainingReport, run_experiment, train_and_save_model
from research.models.mlp_classifier import train_mlp_model
from research.models.train_xgboost import train_xgboost_model
from research.training.label_utils import compute_class_weights, compute_threshold_label


@dataclass
class XGBoostExperimentResult:
    experiment_id: str
    output_dir: Path
    results_dir: Path
    artifacts_dir: Path
    experiment_report: ExperimentReport
    training_report: Optional[ModelTrainingReport]
    training_reports: list[ModelTrainingReport]
    training_report_path: Path


def _wilson_ci(wins: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 0.0
    z = 1.959963984540054
    p_hat = wins / n
    denominator = 1 + z**2 / n
    centre = (p_hat + z**2 / (2 * n)) / denominator
    margin = (z * (p_hat * (1 - p_hat) / n + z**2 / (4 * n**2)) ** 0.5) / denominator
    return float(centre - margin), float(centre + margin)


def _score_test_split(
    model: Any,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    forward_returns: pd.Series,
    fallback_metrics: Dict[str, float],
) -> Dict[str, float]:
    X_eval = X_test.astype(np.float32) if hasattr(X_test, "astype") else X_test
    if hasattr(model, "predict"):
        y_pred = np.asarray(model.predict(X_eval)).astype(int)
    elif hasattr(model, "predict_proba"):
        y_prob = np.asarray(model.predict_proba(X_eval))[:, 1]
        y_pred = (y_prob >= 0.5).astype(int)
    else:
        win_rate = float(fallback_metrics.get("val_accuracy", 0.0))
        fill_rate = float(fallback_metrics.get("val_pos_rate", 0.0))
        n = int(len(y_test))
        wins = int(round(win_rate * n))
        ci_low, ci_high = _wilson_ci(wins, n)
        return {
            "win_rate": win_rate,
            "win_rate_ci_low": ci_low,
            "win_rate_ci_high": ci_high,
            "fill_rate": fill_rate,
            "profit_factor": float(fallback_metrics.get("val_profit_factor", 1.0)),
            "n_closed_trades": n,
        }

    y_true = np.asarray(y_test).astype(int)
    n = int(len(y_true))
    wins = int(np.sum(y_pred == y_true))
    win_rate = float(np.mean(y_pred == y_true)) if n else 0.0
    ci_low, ci_high = _wilson_ci(wins, n)

    trade_mask = y_pred == 1
    trade_returns = forward_returns.loc[X_test.index]
    trade_returns = trade_returns[trade_mask]
    pos_sum = float(trade_returns[trade_returns > 0].sum()) if not trade_returns.empty else 0.0
    neg_sum = float((-trade_returns[trade_returns < 0]).sum()) if not trade_returns.empty else 0.0
    if neg_sum == 0.0:
        profit_factor = float("inf") if pos_sum > 0 else 0.0
    else:
        profit_factor = pos_sum / neg_sum

    return {
        "win_rate": win_rate,
        "win_rate_ci_low": ci_low,
        "win_rate_ci_high": ci_high,
        "fill_rate": float(np.mean(y_pred == 1)) if n else 0.0,
        "profit_factor": float(profit_factor),
        "n_closed_trades": n,
    }


def _split_by_ratio(
    df: pd.DataFrame,
    *,
    train_ratio: float,
    val_ratio: float,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not (0.0 < train_ratio < 1.0):
        raise ValueError("train_ratio must be between 0 and 1")
    if not (0.0 < val_ratio < 1.0):
        raise ValueError("val_ratio must be between 0 and 1")
    if train_ratio + val_ratio >= 1.0:
        raise ValueError("train_ratio + val_ratio must be < 1.0")

    df = df.sort_index()
    total = len(df)
    if total < 10:
        raise ValueError("Not enough rows to split for training")

    train_end = max(1, int(total * train_ratio))
    val_end = max(train_end + 1, int(total * (train_ratio + val_ratio)))
    val_end = min(val_end, total)

    train_df = df.iloc[:train_end]
    val_df = df.iloc[train_end:val_end]
    test_df = df.iloc[val_end:]
    return train_df, val_df, test_df


def _select_feature_columns(features: pd.DataFrame) -> list[str]:
    excluded = {"symbol", "date"}
    return [
        col
        for col in features.columns
        if col not in excluded and pd.api.types.is_numeric_dtype(features[col])
    ]


def _resolve_explainable_model(model: Any) -> Any:
    if hasattr(model, "estimator"):
        return model.estimator
    if hasattr(model, "base_estimator"):
        return model.base_estimator
    return model


def _compute_feature_importance(
    model: Any,
    X_sample: pd.DataFrame,
    feature_cols: list[str],
) -> dict[str, Any]:
    explainable = _resolve_explainable_model(model)

    try:
        import shap

        explainer = shap.TreeExplainer(explainable)
        shap_values = explainer.shap_values(X_sample)
        if isinstance(shap_values, list):
            values = np.asarray(shap_values[-1])
        else:
            values = np.asarray(shap_values)

        if values.ndim == 1:
            values = values.reshape(-1, 1)
        if values.ndim == 3:
            values = values[:, :, -1]

        mean_abs = np.abs(values).mean(axis=0)
        total = float(mean_abs.sum())
        rows = []
        for col, val in zip(feature_cols, mean_abs):
            importance = float(val)
            share = importance / total if total > 0 else 0.0
            rows.append(
                {
                    "feature": col,
                    "importance": round(importance, 10),
                    "share": round(float(share), 10),
                }
            )
        rows.sort(key=lambda item: item["importance"], reverse=True)
        return {
            "source": "shap",
            "top_features": rows[:20],
        }
    except Exception:
        pass

    importances = np.asarray(getattr(explainable, "feature_importances_", np.zeros(len(feature_cols))))
    if importances.shape[0] != len(feature_cols):
        importances = np.zeros(len(feature_cols))
    total = float(importances.sum())
    rows = []
    for col, val in zip(feature_cols, importances):
        importance = float(val)
        share = importance / total if total > 0 else 0.0
        rows.append(
            {
                "feature": col,
                "importance": round(importance, 10),
                "share": round(float(share), 10),
            }
        )
    rows.sort(key=lambda item: item["importance"], reverse=True)
    return {
        "source": "feature_importance_fallback",
        "top_features": rows[:20],
    }


def _resolve_hypothesis_metadata(hypothesis: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not hypothesis:
        return {
            "hypothesis_id": "",
            "hypothesis_text": "",
            "n_prior_tests": 0,
            "registered_before_test": True,
            "adjusted_alpha": 0.05,
        }

    n_prior_tests = int(hypothesis.get("n_prior_tests", 0) or 0)
    adjusted_alpha = 0.05 / (n_prior_tests + 1)
    return {
        "hypothesis_id": str(hypothesis.get("hypothesis_id", "")),
        "hypothesis_text": str(hypothesis.get("hypothesis_text", "")),
        "n_prior_tests": n_prior_tests,
        "registered_before_test": bool(hypothesis.get("registered_before_test", True)),
        "adjusted_alpha": float(adjusted_alpha),
    }


def run_xgboost_experiment(
    *,
    snapshot_dir: str,
    experiment_id: str,
    symbol: str,
    output_dir: str,
    horizon_days: int = 5,
    horizon_id: str = "h5",
    train_ratio: float = 0.6,
    val_ratio: float = 0.2,
    gap_days: int = 0,
    feature_version: str = "v1",
    label_version: str = "h5",
    model_type: str = "xgboost",
    model_id: Optional[str] = None,
    model_params: Optional[Dict[str, Any]] = None,
    calibrate: bool = False,
    label_type: str = "direction",
    threshold_bps: float = 45.0,
    hypothesis: Optional[Dict[str, Any]] = None,
    walk_forward: bool = False,
    train_months: int = 6,
    val_months: int = 3,
    test_months: int = 3,
    step_months: int = 3,
    trainer: Optional[Callable[..., Tuple[Any, Dict[str, float]]]] = None,
) -> XGBoostExperimentResult:
    df, metadata = load_snapshot(snapshot_dir)
    if "symbol" in df.columns:
        df = df[df["symbol"] == symbol].drop(columns=["symbol"])

    if df.empty:
        raise ValueError(f"No rows found for symbol {symbol} in snapshot")

    features = compute_features(df, symbol=symbol)
    cleaned, dropped_rows = drop_nan_rows(features)
    drop_manifest = build_drop_manifest(dropped_rows, len(features))

    close = df["close"].astype(float)
    forward_returns = np.log(close.shift(-horizon_days) / close)

    train_returns = forward_returns.loc[cleaned.index]
    train_returns = train_returns.iloc[: int(len(train_returns) * train_ratio)]
    thresholds = compute_thresholds(train_returns)

    labels = compute_labels(
        df,
        symbol=symbol,
        horizon_days=horizon_days,
        thresholds=thresholds,
        fold_id=1,
        horizon_id=horizon_id,
    )

    resolved_label_type = str(label_type or "direction").strip().lower()
    if resolved_label_type not in {"direction", "threshold"}:
        raise ValueError("label_type must be 'direction' or 'threshold'")
    resolved_model_type = str(model_type or "xgboost").strip().lower()
    if resolved_model_type not in {"xgboost", "mlp"}:
        raise ValueError("model_type must be 'xgboost' or 'mlp'")
    resolved_trainer = trainer
    if resolved_trainer is None:
        resolved_trainer = train_xgboost_model if resolved_model_type == "xgboost" else train_mlp_model
    if resolved_label_type == "threshold":
        labels["label_binary"] = compute_threshold_label(labels["forward_return"], threshold_bps)

    merged = cleaned.join(labels[["label_binary", "forward_return"]], how="inner")
    feature_cols = _select_feature_columns(merged)
    merged = merged.dropna(subset=feature_cols + ["label_binary"])

    run_root = Path(output_dir)
    results_dir = run_root / "results"
    artifacts_dir = run_root / "artifacts"
    shap_dir = run_root / "shap"
    results_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    shap_dir.mkdir(parents=True, exist_ok=True)

    if walk_forward:
        folds = build_walk_forward_folds(
            start=merged.index.min(),
            end=merged.index.max(),
            train_months=train_months,
            val_months=val_months,
            test_months=test_months,
            step_months=step_months,
            gap_days=gap_days,
        )
        if not folds:
            raise ValueError("No walk-forward folds generated for the dataset")

        fold_results = []
        training_reports: list[ModelTrainingReport] = []
        training_payloads: list[dict] = []
        hypothesis_meta = _resolve_hypothesis_metadata(hypothesis)

        for idx, fold in enumerate(folds, start=1):
            train_df = merged.loc[fold["train_start"] : fold["train_end"]]
            val_df = merged.loc[fold["val_start"] : fold["val_end"]]
            test_df = merged.loc[fold["test_start"] : fold["test_end"]]

            if train_df.empty or val_df.empty or test_df.empty:
                continue

            scaler = fit_scaler(train_df, feature_cols)
            train_df = apply_scaler(train_df, scaler, feature_cols)
            val_df = apply_scaler(val_df, scaler, feature_cols)
            test_df = apply_scaler(test_df, scaler, feature_cols)

            X_train = train_df[feature_cols]
            y_train = train_df["label_binary"].astype(int)
            X_val = val_df[feature_cols]
            y_val = val_df["label_binary"].astype(int)
            X_test = test_df[feature_cols]
            y_test = test_df["label_binary"].astype(int)

            fold_model_id = f"{model_id or experiment_id}_xgb_{fold['fold_id']}"
            imbalance_info = compute_class_weights(y_train)
            resolved_params = dict(model_params or {})
            resolved_params["scale_pos_weight"] = imbalance_info["scale_pos_weight"]

            training_report = train_and_save_model(
                model_id=fold_model_id,
                trainer=resolved_trainer,
                trainer_kwargs={
                    "X_train": X_train,
                    "y_train": y_train,
                    "X_val": X_val,
                    "y_val": y_val,
                    "params": resolved_params,
                    "calibrate": calibrate,
                },
                metadata={
                    "model_type": resolved_model_type,
                    "snapshot_id": metadata.get("snapshot_id", "unknown"),
                    "feature_version": feature_version,
                    "label_version": label_version,
                    "train_window": f"{train_df.index.min()}:{train_df.index.max()}",
                    "val_window": f"{val_df.index.min()}:{val_df.index.max()}",
                    "created_at_utc": datetime.now(timezone.utc).isoformat(),
                    "extra_metadata": {
                        "drop_manifest": drop_manifest,
                        "train_rows": int(len(train_df)),
                        "val_rows": int(len(val_df)),
                        "test_rows": int(len(test_df)),
                        "fold_id": fold["fold_id"],
                        "class_distribution": imbalance_info["class_distribution"],
                        "scale_pos_weight_used": imbalance_info["scale_pos_weight"],
                        "label_type": resolved_label_type,
                        "threshold_bps": float(threshold_bps),
                        "n_prior_tests": hypothesis_meta["n_prior_tests"],
                        "adjusted_alpha": hypothesis_meta["adjusted_alpha"],
                        "registered_before_test": hypothesis_meta["registered_before_test"],
                    },
                },
                artifacts_root=artifacts_dir,
            )

            metrics = training_report.metrics
            metrics.setdefault("val_pr_auc", 0.0)
            metrics.setdefault("val_roc_auc", 0.0)
            test_scores = _score_test_split(
                training_report.model,
                X_test,
                y_test,
                test_df["forward_return"],
                metrics,
            )
            shap_payload = _compute_feature_importance(
                training_report.model,
                X_test,
                feature_cols,
            )
            (shap_dir / f"fold_F{fold['fold_id']}.json").write_text(
                json.dumps(
                    {
                        "fold_id": fold["fold_id"],
                        "feature_source": shap_payload["source"],
                        "top_features": shap_payload["top_features"],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            status = "pass"
            if test_scores["n_closed_trades"] < 20:
                status = "insufficient_data"
            elif test_scores["win_rate"] < 0.50:
                status = "fail"

            fold_results.append(
                {
                    "fold_id": fold["fold_id"],
                    "train_start": str(fold["train_start"].date()),
                    "train_end": str(fold["train_end"].date()),
                    "val_start": str(fold["val_start"].date()),
                    "val_end": str(fold["val_end"].date()),
                    "test_start": str(fold["test_start"].date()),
                    "test_end": str(fold["test_end"].date()),
                    "n_closed_trades": test_scores["n_closed_trades"],
                    "win_rate": test_scores["win_rate"],
                    "win_rate_ci_95": [
                        test_scores["win_rate_ci_low"],
                        test_scores["win_rate_ci_high"],
                    ],
                    "profit_factor": test_scores["profit_factor"],
                    "fill_rate": test_scores["fill_rate"],
                    "avg_slippage_pct": float(metrics.get("avg_slippage_pct", 0.0)),
                    "roc_auc": float(metrics.get("val_roc_auc", 0.0)),
                    "pr_auc": float(metrics.get("val_pr_auc", 0.0)),
                    "status": status,
                    "passed": status == "pass",
                    "metrics": metrics,
                }
            )

            training_reports.append(training_report)
            training_payloads.append(
                {
                    "fold_id": fold["fold_id"],
                    "model_id": training_report.model_id,
                    "model_dir": str(training_report.model_dir),
                    "metrics": training_report.metrics,
                    "metadata": training_report.metadata.__dict__,
                    "class_distribution": imbalance_info["class_distribution"],
                    "scale_pos_weight_used": imbalance_info["scale_pos_weight"],
                    "label_type": resolved_label_type,
                    "threshold_bps": float(threshold_bps),
                    "n_prior_tests": hypothesis_meta["n_prior_tests"],
                    "adjusted_alpha": hypothesis_meta["adjusted_alpha"],
                    "registered_before_test": hypothesis_meta["registered_before_test"],
                }
            )

        experiment_report = run_experiment(
            experiment_id=experiment_id,
            fold_results=fold_results,
            output_dir=str(results_dir),
            metadata={
                "snapshot_id": metadata.get("snapshot_id", "unknown"),
                "feature_version": feature_version,
                "label_version": label_version,
                "model_type": resolved_model_type,
                "drop_manifest": drop_manifest,
                "label_type": resolved_label_type,
                "threshold_bps": float(threshold_bps),
                "hypothesis": hypothesis_meta,
            },
        )

        training_report_path = run_root / "training_report.json"
        training_report_path.write_text(
            json.dumps(training_payloads, indent=2),
            encoding="utf-8",
        )

        return XGBoostExperimentResult(
            experiment_id=experiment_id,
            output_dir=run_root,
            results_dir=results_dir,
            artifacts_dir=artifacts_dir,
            experiment_report=experiment_report,
            training_report=None,
            training_reports=training_reports,
            training_report_path=training_report_path,
        )

    train_df, val_df, test_df = _split_by_ratio(
        merged,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
    )
    train_df, val_df, test_df = apply_gap(train_df, val_df, test_df, gap_days=gap_days)

    scaler = fit_scaler(train_df, feature_cols)
    train_df = apply_scaler(train_df, scaler, feature_cols)
    val_df = apply_scaler(val_df, scaler, feature_cols)

    X_train = train_df[feature_cols]
    y_train = train_df["label_binary"].astype(int)
    X_val = val_df[feature_cols]
    y_val = val_df["label_binary"].astype(int)
    X_test = test_df[feature_cols]
    y_test = test_df["label_binary"].astype(int)

    model_suffix = "xgb" if resolved_model_type == "xgboost" else "mlp"
    model_id = model_id or f"{experiment_id}_{model_suffix}"
    imbalance_info = compute_class_weights(y_train)
    resolved_params = dict(model_params or {})
    resolved_params["scale_pos_weight"] = imbalance_info["scale_pos_weight"]
    hypothesis_meta = _resolve_hypothesis_metadata(hypothesis)

    training_report = train_and_save_model(
        model_id=model_id,
        trainer=resolved_trainer,
        trainer_kwargs={
            "X_train": X_train,
            "y_train": y_train,
            "X_val": X_val,
            "y_val": y_val,
            "params": resolved_params,
            "calibrate": calibrate,
        },
        metadata={
            "model_type": resolved_model_type,
            "snapshot_id": metadata.get("snapshot_id", "unknown"),
            "feature_version": feature_version,
            "label_version": label_version,
            "train_window": f"{train_df.index.min()}:{train_df.index.max()}",
            "val_window": f"{val_df.index.min()}:{val_df.index.max()}",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "extra_metadata": {
                "drop_manifest": drop_manifest,
                "train_rows": int(len(train_df)),
                "val_rows": int(len(val_df)),
                "test_rows": int(len(test_df)),
                "class_distribution": imbalance_info["class_distribution"],
                "scale_pos_weight_used": imbalance_info["scale_pos_weight"],
                "label_type": resolved_label_type,
                "threshold_bps": float(threshold_bps),
                "n_prior_tests": hypothesis_meta["n_prior_tests"],
                "adjusted_alpha": hypothesis_meta["adjusted_alpha"],
                "registered_before_test": hypothesis_meta["registered_before_test"],
            },
        },
        artifacts_root=artifacts_dir,
    )

    metrics = training_report.metrics
    metrics.setdefault("val_pr_auc", 0.0)
    metrics.setdefault("val_roc_auc", 0.0)
    test_scores = _score_test_split(
        training_report.model,
        X_test,
        y_test,
        test_df["forward_return"],
        metrics,
    )
    shap_payload = _compute_feature_importance(
        training_report.model,
        X_test,
        feature_cols,
    )
    (shap_dir / "fold_F1.json").write_text(
        json.dumps(
            {
                "fold_id": 1,
                "feature_source": shap_payload["source"],
                "top_features": shap_payload["top_features"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    status = "pass"
    if test_scores["n_closed_trades"] < 20:
        status = "insufficient_data"
    elif test_scores["win_rate"] < 0.50:
        status = "fail"
    fold_results = [
        {
            "n_closed_trades": test_scores["n_closed_trades"],
            "win_rate": test_scores["win_rate"],
            "win_rate_ci_95": [
                test_scores["win_rate_ci_low"],
                test_scores["win_rate_ci_high"],
            ],
            "profit_factor": test_scores["profit_factor"],
            "fill_rate": test_scores["fill_rate"],
            "avg_slippage_pct": float(metrics.get("avg_slippage_pct", 0.0)),
            "roc_auc": float(metrics.get("val_roc_auc", 0.0)),
            "pr_auc": float(metrics.get("val_pr_auc", 0.0)),
            "status": status,
            "passed": status == "pass",
            "metrics": metrics,
        }
    ]

    experiment_report = run_experiment(
        experiment_id=experiment_id,
        fold_results=fold_results,
        output_dir=str(results_dir),
        metadata={
            "snapshot_id": metadata.get("snapshot_id", "unknown"),
            "feature_version": feature_version,
            "label_version": label_version,
            "model_type": resolved_model_type,
            "model_id": training_report.model_id,
            "artifact_hash": training_report.metadata.artifact_hash,
            "drop_manifest": drop_manifest,
            "label_type": resolved_label_type,
            "threshold_bps": float(threshold_bps),
            "hypothesis": hypothesis_meta,
        },
    )

    training_report_path = run_root / "training_report.json"
    training_payload = {
        "model_id": training_report.model_id,
        "model_dir": str(training_report.model_dir),
        "metrics": training_report.metrics,
        "metadata": training_report.metadata.__dict__,
        "class_distribution": imbalance_info["class_distribution"],
        "scale_pos_weight_used": imbalance_info["scale_pos_weight"],
        "label_type": resolved_label_type,
        "threshold_bps": float(threshold_bps),
        "n_prior_tests": hypothesis_meta["n_prior_tests"],
        "adjusted_alpha": hypothesis_meta["adjusted_alpha"],
        "registered_before_test": hypothesis_meta["registered_before_test"],
    }
    training_report_path.write_text(
        json.dumps(training_payload, indent=2),
        encoding="utf-8",
    )

    return XGBoostExperimentResult(
        experiment_id=experiment_id,
        output_dir=run_root,
        results_dir=results_dir,
        artifacts_dir=artifacts_dir,
        experiment_report=experiment_report,
        training_report=training_report,
        training_reports=[training_report],
        training_report_path=training_report_path,
    )
