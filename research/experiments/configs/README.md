# Experiment Configs

This folder stores JSON configs used by the research experiment CLI.

## Required Fields

- `snapshot_dir`
- `experiment_id`
- `symbol`
- `output_dir`

## Optional Fields

- `horizon_days` (default 5)
- `train_ratio` (default 0.6)
- `val_ratio` (default 0.2)
- `gap_days` (default 0)
- `feature_version` (default "v1")
- `label_version` (default "h5")
- `model_id` (optional override)
- `xgb_params` (dict of XGBoost parameters)
- `xgb_preset` (optional preset name from `xgb_params_presets.json`)
- `calibrate` (default false)
- `walk_forward` (default false)
- `train_months` (default 6)
- `val_months` (default 3)
- `test_months` (default 3)
- `step_months` (default 3)

## Example

See `xgboost_example.json` for a starting point.

## Validation Notes

- Unknown keys are rejected to prevent silent config drift.
- Required fields must be present or the loader fails fast.

## Preset Listing

Use this to print available XGBoost presets:

```bash
python main.py research_train_xgboost --print-presets
```
