"""Research experiment orchestration package."""

from research.experiments.config import ExperimentConfig, load_experiment_config
from research.experiments.presets import load_xgb_presets, resolve_xgb_params
from research.experiments.xgboost_pipeline import XGBoostExperimentResult, run_xgboost_experiment

__all__ = [
	"run_xgboost_experiment",
	"XGBoostExperimentResult",
	"ExperimentConfig",
	"load_experiment_config",
	"load_xgb_presets",
	"resolve_xgb_params",
]
