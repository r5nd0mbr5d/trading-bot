"""ML model runtime strategy wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import json
import logging
import pickle

import numpy as np
import pandas as pd

from config.settings import Settings
from research.data.crypto_features import build_crypto_features
from research.data.features import compute_features
from research.models.artifacts import compute_sha256
from src.data.models import AssetClass, Signal, SignalType
from src.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


@dataclass
class ModelBundle:
    model: Any
    model_type: str
    model_path: str
    metadata: dict[str, Any]
    asset_class: AssetClass


def _load_model_from_path(model_path: Path, model_type: str) -> Any:
    normalized_type = (model_type or "").strip().lower()
    if normalized_type == "xgboost" and model_path.suffix in {".bin", ".json", ".txt"}:
        try:
            import xgboost as xgb
        except ImportError as exc:
            raise RuntimeError("xgboost is required to load xgboost artifacts") from exc
        model = xgb.XGBClassifier()
        model.load_model(str(model_path))
        return model

    if model_path.suffix == ".pt":
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError("torch is required to load .pt model artifacts") from exc
        return torch.load(str(model_path), map_location="cpu")

    with model_path.open("rb") as handle:
        return pickle.load(handle)


def load_model_bundle(model_path: str) -> ModelBundle:
    resolved_path = Path(model_path)
    metadata_path = resolved_path.parent / "metadata.json"
    metadata: dict[str, Any] = {}
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text())

    expected_hash = str(metadata.get("artifact_hash", "")).strip()
    if expected_hash:
        computed_hash = compute_sha256(resolved_path)
        if computed_hash != expected_hash:
            raise ValueError("Model artifact hash mismatch")

    model_type = str(metadata.get("model_type", "")).strip().lower()
    if not model_type:
        if resolved_path.suffix in {".bin", ".json", ".txt"}:
            model_type = "xgboost"
        elif resolved_path.suffix == ".pt":
            model_type = "mlp"
        else:
            model_type = "mlp"

    extra_metadata = metadata.get("extra_metadata")
    if isinstance(extra_metadata, dict):
        raw_asset_class = extra_metadata.get("asset_class", metadata.get("asset_class", "equity"))
    else:
        raw_asset_class = metadata.get("asset_class", "equity")

    normalized_asset = str(raw_asset_class).strip().lower()
    if normalized_asset in {"crypto", "assetclass.crypto"}:
        asset_class = AssetClass.CRYPTO
    elif normalized_asset in {"forex", "assetclass.forex"} and hasattr(AssetClass, "FOREX"):
        asset_class = AssetClass.FOREX
    else:
        asset_class = AssetClass.EQUITY

    model = _load_model_from_path(resolved_path, model_type)
    return ModelBundle(
        model=model,
        model_type=model_type,
        model_path=str(resolved_path),
        metadata=metadata,
        asset_class=asset_class,
    )


class MLStrategyWrapper(BaseStrategy):
    """Use trained research artifacts to emit runtime trading signals."""

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self._threshold = float(settings.strategy.model_threshold)
        model_paths = [path.strip() for path in settings.strategy.model_path.split(",") if path.strip()]
        if not model_paths:
            raise ValueError("MLStrategyWrapper requires settings.strategy.model_path")

        self._bundles = [load_model_bundle(path) for path in model_paths]
        self._expected_asset_class = self._bundles[0].asset_class

    def min_bars_required(self) -> int:
        for bundle in self._bundles:
            metadata_min = bundle.metadata.get("min_bars_required")
            if metadata_min is not None:
                try:
                    return int(metadata_min)
                except (TypeError, ValueError):
                    continue
        if self._expected_asset_class == AssetClass.CRYPTO:
            return 61
        return 201

    def _symbol_asset_class_matches(self, symbol: str) -> bool:
        symbol_asset_class = self.settings.get_symbol_asset_class(symbol)
        return symbol_asset_class == self._expected_asset_class

    def _build_feature_frame(self, symbol: str) -> pd.DataFrame:
        history = self.get_history_df(symbol)
        if history.empty:
            return pd.DataFrame()

        if self._expected_asset_class == AssetClass.CRYPTO:
            features = build_crypto_features(history)
        else:
            features = compute_features(history, symbol=symbol)

        if features.empty:
            return pd.DataFrame()

        latest = features.iloc[[-1]].copy()
        for drop_col in ("symbol", "date"):
            if drop_col in latest.columns:
                latest = latest.drop(columns=[drop_col])

        numeric = latest.select_dtypes(include=[np.number]).replace([np.inf, -np.inf], np.nan)
        numeric = numeric.ffill().bfill()
        if numeric.isna().any(axis=1).iloc[0]:
            return pd.DataFrame()
        return numeric

    @staticmethod
    def _predict_probability(model: Any, feature_frame: pd.DataFrame) -> float:
        if hasattr(model, "predict_proba"):
            probs = np.asarray(model.predict_proba(feature_frame))
            if probs.ndim == 2 and probs.shape[1] >= 2:
                return float(probs[0, 1])
            return float(probs.reshape(-1)[0])

        if hasattr(model, "predict"):
            values = np.asarray(model.predict(feature_frame))
            return float(values.reshape(-1)[0])

        if callable(model):
            values = np.asarray(model(feature_frame.to_numpy(dtype=float)))
            return float(values.reshape(-1)[0])

        raise ValueError("Model does not expose predict_proba/predict/callable interface")

    def _get_probability(self, feature_frame: pd.DataFrame) -> tuple[float, list[float]]:
        probabilities: list[float] = []
        for bundle in self._bundles:
            probability = self._predict_probability(bundle.model, feature_frame)
            probabilities.append(float(np.clip(probability, 0.0, 1.0)))

        mean_probability = float(np.mean(probabilities))
        return mean_probability, probabilities

    def _resolve_signal_type(self, probabilities: list[float]) -> SignalType | None:
        long_votes = sum(prob >= self._threshold for prob in probabilities)
        close_votes = sum(prob <= (1.0 - self._threshold) for prob in probabilities)

        if long_votes > close_votes and long_votes > 0:
            return SignalType.LONG
        if close_votes > long_votes and close_votes > 0:
            return SignalType.CLOSE
        return None

    def generate_signal(self, symbol: str) -> Optional[Signal]:
        history = self.get_history_df(symbol)
        if len(history) < self.min_bars_required():
            return None

        if not self._symbol_asset_class_matches(symbol):
            logger.warning(
                "ML strategy asset-class mismatch for symbol %s: expected=%s got=%s",
                symbol,
                self._expected_asset_class.value,
                self.settings.get_symbol_asset_class(symbol).value,
            )
            return None

        feature_frame = self._build_feature_frame(symbol)
        if feature_frame.empty:
            return None

        mean_probability, probabilities = self._get_probability(feature_frame)
        signal_type = self._resolve_signal_type(probabilities)
        if signal_type is None:
            return None

        timestamp = history.index[-1]
        signal_timestamp: datetime = (
            timestamp.to_pydatetime() if hasattr(timestamp, "to_pydatetime") else timestamp
        )

        if signal_type == SignalType.LONG:
            strength = float(np.clip(mean_probability, 0.0, 1.0))
        else:
            strength = float(np.clip(1.0 - mean_probability, 0.0, 1.0))

        return Signal(
            symbol=symbol,
            signal_type=signal_type,
            strength=strength,
            timestamp=signal_timestamp,
            strategy_name=self.name,
            metadata={
                "prediction_confidence": mean_probability,
                "ensemble_size": len(self._bundles),
                "model_probabilities": probabilities,
                "model_paths": [bundle.model_path for bundle in self._bundles],
            },
        )
