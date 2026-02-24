import json

import pytest

from research.experiments.config import ExperimentConfig, load_experiment_config


def test_load_experiment_config(tmp_path):
    config_path = tmp_path / "config.json"
    payload = {
        "snapshot_dir": "research/data/snapshots/snap_1",
        "experiment_id": "xgb_test",
        "symbol": "TEST",
        "output_dir": "research/experiments/xgb_test",
        "horizon_days": 7,
        "train_ratio": 0.7,
        "val_ratio": 0.15,
        "gap_days": 2,
        "feature_version": "v2",
        "label_version": "h7",
        "model_id": "xgb_test_model",
        "xgb_params": {"max_depth": 3},
        "xgb_preset": "medium",
        "calibrate": True,
    }
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    config = load_experiment_config(config_path)

    assert isinstance(config, ExperimentConfig)
    assert config.snapshot_dir == payload["snapshot_dir"]
    assert config.experiment_id == payload["experiment_id"]
    assert config.symbol == payload["symbol"]
    assert config.output_dir == payload["output_dir"]
    assert config.horizon_days == 7
    assert config.train_ratio == 0.7
    assert config.val_ratio == 0.15
    assert config.gap_days == 2
    assert config.feature_version == "v2"
    assert config.label_version == "h7"
    assert config.model_id == "xgb_test_model"
    assert config.xgb_params == {"max_depth": 3}
    assert config.xgb_preset == "medium"
    assert config.calibrate is True


def test_load_experiment_config_requires_fields(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"experiment_id": "xgb_test"}), encoding="utf-8")

    with pytest.raises(ValueError, match="Missing required config fields"):
        load_experiment_config(config_path)


def test_load_experiment_config_rejects_unknown_fields(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "snapshot_dir": "snap",
                "experiment_id": "xgb_test",
                "symbol": "TEST",
                "output_dir": "out",
                "extra": "nope",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unknown config fields"):
        load_experiment_config(config_path)


def test_load_experiment_config_rejects_bad_types(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "snapshot_dir": 123,
                "experiment_id": "xgb_test",
                "symbol": "TEST",
                "output_dir": "out",
                "xgb_params": "nope",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="snapshot_dir must be a string"):
        load_experiment_config(config_path)


def test_load_experiment_config_rejects_bad_ranges(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "snapshot_dir": "snap",
                "experiment_id": "xgb_test",
                "symbol": "TEST",
                "output_dir": "out",
                "horizon_days": 0,
                "train_ratio": 0.9,
                "val_ratio": 0.2,
                "gap_days": -1,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="horizon_days must be positive"):
        load_experiment_config(config_path)
