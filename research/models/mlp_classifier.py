"""Feedforward MLP training utility for research experiments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np

try:
    from torch import nn as torch_nn
except ImportError:
    torch_nn = None


@dataclass(frozen=True)
class MLPTrainingConfig:
    """Resolved MLP training configuration.

    Parameters
    ----------
    hidden_sizes : tuple[int, int, int]
        Hidden layer sizes in order.
    dropout : float
        Dropout probability for hidden layers.
    learning_rate : float
        Initial optimizer learning rate.
    batch_size : int
        Batch size used by skorch.
    max_epochs : int
        Maximum number of training epochs.
    early_stopping_patience : int
        Patience value for early stopping callback.
    gamma : float
        Exponential learning rate decay factor.
    random_state : int
        Random seed for reproducibility.
    scale_pos_weight : float
        Positive-class weight used in BCEWithLogitsLoss.
    """

    hidden_sizes: tuple[int, int, int] = (128, 64, 32)
    dropout: float = 0.3
    learning_rate: float = 1e-3
    batch_size: int = 128
    max_epochs: int = 60
    early_stopping_patience: int = 10
    gamma: float = 0.9
    random_state: int = 42
    scale_pos_weight: float = 1.0


if torch_nn is not None:
    class FeedForwardBinaryClassifier(torch_nn.Module):
        """Pickle-safe feedforward torch module for binary classification."""

        def __init__(
            self,
            input_dim: int,
            hidden_size_1: int = 128,
            hidden_size_2: int = 64,
            hidden_size_3: int = 32,
            dropout: float = 0.3,
        ) -> None:
            super().__init__()
            self.layers = torch_nn.Sequential(
                torch_nn.Linear(input_dim, hidden_size_1),
                torch_nn.ReLU(),
                torch_nn.Dropout(dropout),
                torch_nn.Linear(hidden_size_1, hidden_size_2),
                torch_nn.ReLU(),
                torch_nn.Dropout(dropout),
                torch_nn.Linear(hidden_size_2, hidden_size_3),
                torch_nn.ReLU(),
                torch_nn.Dropout(dropout),
                torch_nn.Linear(hidden_size_3, 1),
            )

        def forward(self, values: Any) -> Any:
            return self.layers(values).squeeze(-1)
else:
    class FeedForwardBinaryClassifier:
        """Placeholder class when torch is unavailable at import time."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("torch is required to construct FeedForwardBinaryClassifier")


def _binary_log_loss(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    eps = 1e-15
    clipped = np.clip(y_prob, eps, 1 - eps)
    loss = -(y_true * np.log(clipped) + (1 - y_true) * np.log(1 - clipped))
    return float(np.mean(loss))


def _resolve_config(params: Optional[Dict[str, Any]]) -> MLPTrainingConfig:
    if not params:
        return MLPTrainingConfig()

    hidden_sizes = (
        int(params.get("hidden_size_1", 128)),
        int(params.get("hidden_size_2", 64)),
        int(params.get("hidden_size_3", 32)),
    )
    return MLPTrainingConfig(
        hidden_sizes=hidden_sizes,
        dropout=float(params.get("dropout", 0.3)),
        learning_rate=float(params.get("learning_rate", 1e-3)),
        batch_size=int(params.get("batch_size", 128)),
        max_epochs=int(params.get("max_epochs", 60)),
        early_stopping_patience=int(params.get("early_stopping_patience", 10)),
        gamma=float(params.get("gamma", 0.9)),
        random_state=int(params.get("random_state", 42)),
        scale_pos_weight=max(float(params.get("scale_pos_weight", 1.0)), 1e-6),
    )


def _to_numpy(values: Any) -> np.ndarray:
    if hasattr(values, "to_numpy"):
        return values.to_numpy()
    return np.asarray(values)


def train_mlp_model(
    X_train: Any,
    y_train: Any,
    X_val: Any,
    y_val: Any,
    *,
    params: Optional[Dict[str, Any]] = None,
    calibrate: bool = False,
) -> Tuple[Any, Dict[str, float]]:
    """Train a feedforward MLP classifier and return model + validation metrics.

    Parameters
    ----------
    X_train : Any
        Training features.
    y_train : Any
        Training labels.
    X_val : Any
        Validation features.
    y_val : Any
        Validation labels.
    params : Optional[Dict[str, Any]], optional
        Optional hyperparameter overrides, by default None.
    calibrate : bool, optional
        If True, applies sigmoid calibration on validation data, by default False.

    Returns
    -------
    Tuple[Any, Dict[str, float]]
        Trained model and validation metrics.

    Raises
    ------
    RuntimeError
        If required ML dependencies are not installed.
    """
    try:
        import torch
        from sklearn.calibration import CalibratedClassifierCV
        from sklearn.metrics import average_precision_score, roc_auc_score
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        from skorch import NeuralNetBinaryClassifier
        from skorch.callbacks import EarlyStopping, LRScheduler
        from skorch.dataset import Dataset
        from skorch.helper import predefined_split
        from torch import nn
    except ImportError as exc:
        raise RuntimeError("MLP training requires torch, scikit-learn, and skorch") from exc

    config = _resolve_config(params)
    torch.manual_seed(config.random_state)
    np.random.seed(config.random_state)

    X_train_np = _to_numpy(X_train).astype(np.float32)
    X_val_np = _to_numpy(X_val).astype(np.float32)
    y_train_np = _to_numpy(y_train).astype(np.float32)
    y_val_np = _to_numpy(y_val).astype(np.float32)

    validation_dataset = Dataset(X_val_np, y_val_np)
    pos_weight_tensor = torch.tensor([config.scale_pos_weight], dtype=torch.float32)
    net = NeuralNetBinaryClassifier(
        module=FeedForwardBinaryClassifier,
        module__input_dim=int(X_train_np.shape[1]),
        module__hidden_size_1=config.hidden_sizes[0],
        module__hidden_size_2=config.hidden_sizes[1],
        module__hidden_size_3=config.hidden_sizes[2],
        module__dropout=config.dropout,
        criterion=nn.BCEWithLogitsLoss,
        criterion__pos_weight=pos_weight_tensor,
        optimizer=torch.optim.Adam,
        optimizer__lr=config.learning_rate,
        batch_size=config.batch_size,
        max_epochs=config.max_epochs,
        train_split=predefined_split(validation_dataset),
        callbacks=[
            (
                "early_stopping",
                EarlyStopping(patience=config.early_stopping_patience, monitor="valid_loss"),
            ),
            (
                "lr_scheduler",
                LRScheduler(policy="ExponentialLR", gamma=config.gamma),
            ),
        ],
        iterator_train__shuffle=True,
        verbose=0,
    )

    model = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("mlp", net),
        ]
    )
    model.fit(X_train_np, y_train_np)

    y_prob = np.asarray(model.predict_proba(X_val_np))[:, 1]
    y_pred = (y_prob >= 0.5).astype(int)
    y_val_int = y_val_np.astype(int)

    try:
        val_roc_auc = float(roc_auc_score(y_val_int, y_prob))
        val_pr_auc = float(average_precision_score(y_val_int, y_prob))
    except Exception:
        val_roc_auc = 0.0
        val_pr_auc = 0.0

    metrics = {
        "val_logloss": _binary_log_loss(y_val_int, y_prob),
        "val_accuracy": float(np.mean(y_pred == y_val_int)),
        "val_pos_rate": float(np.mean(y_pred)),
        "val_roc_auc": val_roc_auc,
        "val_pr_auc": val_pr_auc,
    }

    if calibrate:
        calibrated = CalibratedClassifierCV(model, method="sigmoid", cv="prefit")
        calibrated.fit(X_val_np, y_val_int)
        model = calibrated

    return model, metrics
