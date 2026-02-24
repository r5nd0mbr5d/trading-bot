"""Preset loading helpers for research experiments."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import json


def load_xgb_presets(path: str | Path) -> Dict[str, Dict[str, Any]]:
    presets_path = Path(path)
    if not presets_path.exists():
        raise FileNotFoundError(f"XGBoost presets not found: {presets_path}")
    payload = json.loads(presets_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("XGBoost presets must be a JSON object")
    return payload


def resolve_xgb_params(
    *,
    preset_name: Optional[str],
    explicit_params: Optional[Dict[str, Any]],
    presets_path: str | Path,
) -> Optional[Dict[str, Any]]:
    if explicit_params:
        return explicit_params
    if not preset_name:
        return None

    presets = load_xgb_presets(presets_path)
    preset = presets.get(preset_name)
    if preset is None:
        raise ValueError(f"Unknown XGBoost preset: {preset_name}")
    if not isinstance(preset, dict):
        raise ValueError(f"Preset {preset_name} must be a JSON object")
    return preset
