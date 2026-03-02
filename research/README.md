# Research Track (Global Strategy R&D — UK-Based)

Purpose: develop and evaluate new profit-seeking strategies offline across global equity markets, then promote only validated candidates into runtime.

## Why this stays in the same repo

- Reuses existing strategy interfaces, risk controls, and audit/promotion tooling
- Keeps research-to-runtime handoff explicit and testable
- Prevents drift between experimental assumptions and production behavior

Use a separate repo only if team ownership or infrastructure diverges significantly.

## Operating model

1. Build reproducible offline datasets (`research/data/snapshots/`)
2. Engineer features and labels (`research/data/features/`)
3. Run experiments (`research/experiments/`) and store artifacts (`research/models/`)
4. Evaluate with walk-forward and regime-split validation
5. Convert top candidates into runtime-compatible strategies/configs
6. Promote only through existing paper-trial and checklist gates

## Directory layout

```text
research/
  README.md
  prompts/
    UK_STRATEGY_PROMPTS.md
  tickets/
    UK_RESEARCH_TICKETS.md
  data/
    snapshots/
    features/
  experiments/
    notebooks/
    runs/
  models/
    artifacts/
    metadata/
```

## Promotion contract

A strategy candidate can be promoted only if it includes:

- dataset snapshot metadata (source universe, date range, hash)
- experiment reproducibility metadata (config, seed, feature set)
- out-of-sample + walk-forward evidence
- paper-trial pass evidence via current runtime workflow

## Quickstart (XGBoost demo)

Run the end-to-end demo to generate a snapshot, config, and experiment outputs:

```bash
python research/experiments/examples/end_to_end_xgb_demo.py
```

Use a config file directly with the CLI pipeline:

```bash
python main.py research_train_xgboost --config research/experiments/configs/xgboost_example.json
```

Print the resolved config or list presets:

```bash
python main.py research_train_xgboost --config research/experiments/configs/xgboost_example.json --dry-run
python main.py research_train_xgboost --print-presets
```

## CLI Flags (XGBoost pipeline)

- `--config`: load experiment config JSON
- `--xgb-preset`: choose preset from `xgb_params_presets.json`
- `--xgb-params-json`: override params via JSON file
- `--dry-run`: print resolved config and exit
- `--print-presets`: list available presets and exit

Historical tick backlog download (Polygon):

```bash
python main.py research_download_ticks --tick-provider polygon --symbols AAPL --tick-date 2026-02-20 --tick-api-key <POLYGON_API_KEY>

# Backfill multiple days
python main.py research_download_ticks --tick-provider polygon --symbols AAPL --tick-start-date 2026-02-20 --tick-end-date 2026-02-22 --tick-api-key <POLYGON_API_KEY>

# Backfill + reproducible manifest (hashes/rows/time-ranges)
python main.py research_download_ticks --tick-provider polygon --symbols AAPL --tick-start-date 2026-02-20 --tick-end-date 2026-02-22 --tick-api-key <POLYGON_API_KEY> --tick-build-manifest
```

Use `research.data.tick_dataset` to load ticks from `tick_backlog_manifest.json` and split into train/val/test by date cutoffs.

Build reproducible train/val/test CSV bundles from a manifest:

```bash
python main.py research_build_tick_splits --tick-input-manifest research/data/ticks/tick_backlog_manifest.json --symbols AAPL --tick-start-date 2026-02-20 --tick-end-date 2026-02-22 --tick-train-end 2026-02-20T23:59:59Z --tick-val-end 2026-02-21T23:59:59Z --tick-split-output-dir research/data/ticks/splits
```

Expected outputs (demo or pipeline run):

- `research/experiments/<experiment_id>/results/aggregate_summary.json`
- `research/experiments/<experiment_id>/results/promotion_check.json`
- `research/experiments/<experiment_id>/results/fold_F1.json`
- `research/experiments/<experiment_id>/artifacts/<model_id>/model.bin`
- `research/experiments/<experiment_id>/artifacts/<model_id>/metadata.json`
- `research/experiments/<experiment_id>/training_report.json`

## Troubleshooting

- **Snapshot not found**: ensure `snapshot_dir` points to a folder containing `dataset.csv` and `metadata.json`.
- **Snapshot hash mismatch**: the dataset or metadata was modified after creation; regenerate the snapshot.
- **No rows for symbol**: the snapshot does not include the requested `symbol` column or symbol values; verify the dataset.
- **Not enough rows to split**: increase the snapshot window or reduce `horizon_days` to retain usable rows.

## UK-based operational defaults

- Base currency: GBP
- Session assumptions: UK/London session as default guardrail; exchange-specific sessions for non-UK markets
- Tax/report compatibility: preserve UK export compatibility (`uk_tax_export` flow)
- Research baseline universe: FTSE 100/250 + liquid ETFs for initial validation
- Expanded universe: US, European, Asian, and other global equities accessible via IBKR/EODHD — add when hypothesis requires cross-market signals, sector rotation, or diversification analysis
