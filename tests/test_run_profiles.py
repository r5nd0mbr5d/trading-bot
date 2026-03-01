"""Tests for Step 103 JSON run profiles and merge precedence."""

from __future__ import annotations

import argparse
import json

import pytest

from config.settings import Settings
from src.cli.arguments import apply_common_settings, build_argument_parser
from src.cli.runtime import apply_runtime_profile


def _base_args(**overrides) -> argparse.Namespace:
    payload = {
        "profile": "default",
        "strategy": None,
        "capital": None,
        "broker": None,
        "no_market_hours": False,
        "auto_rotate_paper_db": False,
        "no_auto_rotate_paper_db": False,
        "symbols": None,
        "asset_class": None,
        "model_path": None,
    }
    payload.update(overrides)
    return argparse.Namespace(**payload)


def test_apply_runtime_profile_loads_json_profile(tmp_path) -> None:
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "asset_class": "crypto",
                "symbols": ["BTCGBP"],
                "strategy": "rsi_momentum",
                "broker": "alpaca",
                "risk": {"max_position_pct": 0.2},
            }
        )
    )

    settings = Settings()
    apply_runtime_profile(settings, str(profile_path))

    assert settings.data.asset_class == "crypto"
    assert settings.data.symbols == ["BTCGBP"]
    assert settings.strategy.name == "rsi_momentum"
    assert settings.broker.provider == "alpaca"
    assert settings.crypto_risk.max_position_pct == 0.2


def test_apply_runtime_profile_rejects_malformed_symbols(tmp_path) -> None:
    profile_path = tmp_path / "bad_profile.json"
    profile_path.write_text(json.dumps({"symbols": "BTCGBP"}))

    with pytest.raises(ValueError):
        apply_runtime_profile(Settings(), str(profile_path))


def test_explicit_args_override_profile_defaults(tmp_path) -> None:
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "asset_class": "crypto",
                "symbols": ["BTCGBP"],
                "strategy": "rsi_momentum",
                "model_path": "profile_model.bin",
            }
        )
    )

    settings = Settings()
    args = _base_args(
        profile=str(profile_path),
        strategy="ma_crossover",
        symbols=["HSBA.L"],
        asset_class="equity",
        model_path="cli_model.bin",
    )

    apply_common_settings(args, settings, apply_runtime_profile)

    assert settings.strategy.name == "ma_crossover"
    assert settings.data.symbols == ["HSBA.L"]
    assert settings.data.asset_class == "equity"
    assert settings.strategy.model_path == "cli_model.bin"


def test_parser_accepts_json_profile_path() -> None:
    parser = build_argument_parser(["ma_crossover", "rsi_momentum", "ml_model"])
    args = parser.parse_args(["backtest", "--profile", "configs/profile_uk_equity.json"])

    assert args.profile == "configs/profile_uk_equity.json"
    assert args.strategy is None
