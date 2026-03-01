"""Tests for ML strategy runtime wrapper (Step 101)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from config.settings import Settings
from src.data.models import AssetClass, Bar, SignalType
from src.strategies import ml_wrapper
from src.strategies.ml_wrapper import MLStrategyWrapper, ModelBundle


class _DummyModel:
    def __init__(self, probability: float) -> None:
        self._probability = probability

    def predict_proba(self, frame: pd.DataFrame):
        _ = frame
        return [[1.0 - self._probability, self._probability]]


def _make_bundle(probability: float, asset_class: AssetClass = AssetClass.EQUITY) -> ModelBundle:
    return ModelBundle(
        model=_DummyModel(probability),
        model_type="xgboost",
        model_path="dummy_model.bin",
        metadata={"model_type": "xgboost", "asset_class": asset_class.value, "min_bars_required": 1},
        asset_class=asset_class,
    )


def _make_bar(symbol: str, index: int) -> Bar:
    timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=index)
    close = 100.0 + float(index)
    return Bar(
        symbol=symbol,
        timestamp=timestamp,
        open=close,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        volume=1000.0,
    )


def test_requires_model_path() -> None:
    settings = Settings()
    settings.strategy.model_path = ""

    with pytest.raises(ValueError):
        MLStrategyWrapper(settings)


def test_prediction_converts_to_long_signal(monkeypatch) -> None:
    monkeypatch.setattr(ml_wrapper, "load_model_bundle", lambda _path: _make_bundle(0.8))

    settings = Settings()
    settings.strategy.model_path = "dummy_model.bin"
    settings.strategy.model_threshold = 0.6

    strategy = MLStrategyWrapper(settings)
    monkeypatch.setattr(
        strategy,
        "_build_feature_frame",
        lambda _symbol: pd.DataFrame({"f1": [1.0], "f2": [2.0]}),
    )

    signal = strategy.on_bar(_make_bar("AAPL", 0))

    assert signal is not None
    assert signal.signal_type == SignalType.LONG
    assert signal.metadata["prediction_confidence"] == 0.8
    assert signal.metadata["ensemble_size"] == 1


def test_asset_class_mismatch_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(
        ml_wrapper,
        "load_model_bundle",
        lambda _path: _make_bundle(0.9, asset_class=AssetClass.CRYPTO),
    )

    settings = Settings()
    settings.strategy.model_path = "dummy_model.bin"

    strategy = MLStrategyWrapper(settings)
    monkeypatch.setattr(
        strategy,
        "_build_feature_frame",
        lambda _symbol: pd.DataFrame({"f1": [1.0], "f2": [2.0]}),
    )

    signal = strategy.on_bar(_make_bar("AAPL", 0))
    assert signal is None


def test_ensemble_majority_vote(monkeypatch) -> None:
    bundles = [_make_bundle(0.8), _make_bundle(0.75), _make_bundle(0.2)]

    def _loader(path: str) -> ModelBundle:
        index = 0 if path.endswith("1.bin") else 1 if path.endswith("2.bin") else 2
        return bundles[index]

    monkeypatch.setattr(ml_wrapper, "load_model_bundle", _loader)

    settings = Settings()
    settings.strategy.model_path = "m1.bin,m2.bin,m3.bin"
    settings.strategy.model_threshold = 0.6

    strategy = MLStrategyWrapper(settings)
    monkeypatch.setattr(
        strategy,
        "_build_feature_frame",
        lambda _symbol: pd.DataFrame({"f1": [1.0], "f2": [2.0]}),
    )

    signal = strategy.on_bar(_make_bar("AAPL", 0))

    assert signal is not None
    assert signal.signal_type == SignalType.LONG
    assert signal.metadata["ensemble_size"] == 3
    assert len(signal.metadata["model_probabilities"]) == 3
