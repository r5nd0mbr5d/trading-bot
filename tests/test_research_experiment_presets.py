import json

import pytest

from research.experiments.presets import load_xgb_presets, resolve_xgb_params


def test_load_xgb_presets(tmp_path):
    presets_path = tmp_path / "presets.json"
    presets_path.write_text(json.dumps({"small": {"max_depth": 3}}), encoding="utf-8")

    presets = load_xgb_presets(presets_path)
    assert presets["small"]["max_depth"] == 3


def test_resolve_xgb_params_prefers_explicit(tmp_path):
    presets_path = tmp_path / "presets.json"
    presets_path.write_text(json.dumps({"small": {"max_depth": 3}}), encoding="utf-8")

    params = resolve_xgb_params(
        preset_name="small",
        explicit_params={"max_depth": 5},
        presets_path=presets_path,
    )
    assert params["max_depth"] == 5


def test_resolve_xgb_params_uses_preset(tmp_path):
    presets_path = tmp_path / "presets.json"
    presets_path.write_text(json.dumps({"medium": {"max_depth": 4}}), encoding="utf-8")

    params = resolve_xgb_params(
        preset_name="medium",
        explicit_params=None,
        presets_path=presets_path,
    )
    assert params["max_depth"] == 4


def test_resolve_xgb_params_unknown_preset(tmp_path):
    presets_path = tmp_path / "presets.json"
    presets_path.write_text(json.dumps({"small": {"max_depth": 3}}), encoding="utf-8")

    with pytest.raises(ValueError, match="Unknown XGBoost preset"):
        resolve_xgb_params(
            preset_name="large",
            explicit_params=None,
            presets_path=presets_path,
        )
