"""XGBoost training utility for research experiments."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np


DEFAULT_XGB_PARAMS: Dict[str, Any] = {
    "objective": "binary:logistic",
    "n_estimators": 300,
    "max_depth": 4,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 10,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "scale_pos_weight": 1.0,
    "eval_metric": ["logloss", "auc"],
    "early_stopping_rounds": 30,
    "random_state": 42,
    "n_jobs": -1,
}


def _binary_log_loss(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    eps = 1e-15
    clipped = np.clip(y_prob, eps, 1 - eps)
    loss = -(y_true * np.log(clipped) + (1 - y_true) * np.log(1 - clipped))
    return float(np.mean(loss))


def train_xgboost_model(
    X_train: Any,
    y_train: Any,
    X_val: Any,
    y_val: Any,
    *,
    params: Optional[Dict[str, Any]] = None,
    calibrate: bool = False,
) -> Tuple[Any, Dict[str, float]]:
    try:
        import xgboost as xgb
    except ImportError as exc:
        raise RuntimeError("xgboost is required to train the baseline model") from exc

    merged = dict(DEFAULT_XGB_PARAMS)
    if params:
        merged.update(params)

    model = xgb.XGBClassifier(**merged)
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    y_prob = model.predict_proba(X_val)[:, 1]
    y_pred = (y_prob >= 0.5).astype(int)
    y_val_np = np.asarray(y_val)

    try:
        from sklearn.metrics import average_precision_score, roc_auc_score

        val_roc_auc = float(roc_auc_score(y_val_np, y_prob))
        val_pr_auc = float(average_precision_score(y_val_np, y_prob))
    except Exception:
        val_roc_auc = 0.0
        val_pr_auc = 0.0

    metrics = {
        "val_logloss": _binary_log_loss(y_val_np, y_prob),
        "val_accuracy": float(np.mean(y_pred == y_val_np)),
        "val_pos_rate": float(np.mean(y_pred)),
        "val_roc_auc": val_roc_auc,
        "val_pr_auc": val_pr_auc,
    }

    if calibrate:
        try:
            from sklearn.calibration import CalibratedClassifierCV
        except ImportError as exc:
            raise RuntimeError("scikit-learn is required for calibration") from exc

        calibrated = CalibratedClassifierCV(model, method="sigmoid", cv="prefit")
        calibrated.fit(X_val, y_val)
        model = calibrated

    return model, metrics
