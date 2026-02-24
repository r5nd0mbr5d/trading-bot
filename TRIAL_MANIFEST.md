# Trial Manifest — Simplified Paper Trading Configuration

## Overview

Trial Manifests enable reproducible, configuration-driven paper trading sessions. Instead of typing long CLI arguments, you define all settings (profile, strategy, duration, KPI targets, tolerances) once in a JSON file and invoke them with a single flag.

## Usage

### Run a trial with a manifest:
```bash
python main.py paper_trial --manifest configs/trial_standard.json
```

### Three preset profiles available:

#### Conservative (High Bar)
```bash
python main.py paper_trial --manifest configs/trial_conservative.json
```
- **Duration**: 1 hour (3600 seconds)
- **Symbols**: MSFT, AAPL, NVDA
- **Expected KPIs**:
  - Min 30 closed trades
  - ≥58% win rate
  - Profit factor ≥1.35
  - Realized P&L ≥$500
- **Tolerances**: Tight (e.g., ±3% on fill rate)
- **Drift Exit**: Yes (--strict-reconcile, exit code 1 on drift)
- **Use case**: Pre-live validation—only promote if this passes cleanly

#### Standard (Baseline)
```bash
python main.py paper_trial --manifest configs/trial_standard.json
```
- **Duration**: 15 minutes (900 seconds)
- **Symbols**: MSFT, AAPL, NVDA
- **Expected KPIs**:
  - Min 20 closed trades
  - ≥50% win rate
  - Profit factor ≥1.10
  - Realized P&L ≥$0
- **Tolerances**: Moderate (e.g., ±5% on fill rate)
- **Drift Exit**: No (warnings only)
- **Use case**: Daily health checks—quick smoke test

#### Aggressive (Permissive)
```bash
python main.py paper_trial --manifest configs/trial_aggressive.json
```
- **Duration**: 5 minutes (300 seconds)
- **Symbols**: MSFT, AAPL
- **Expected KPIs**:
  - Min 12 closed trades
  - ≥44% win rate
  - Profit factor ≥1.0
  - Realized P&L ≥-$250
- **Tolerances**: Loose (e.g., ±8% on fill rate)
- **Drift Exit**: No
- **Use case**: Quick integration test—catch major breaks only

## Manifest Structure

```json
{
  "name": "My Custom Trial",
  "profile": "uk_paper",
  "strategy": "ma_crossover",
  "duration_seconds": 900,
  "symbols": ["MSFT", "AAPL", "NVDA"],
  "capital": 100000.0,
  "expected_json": "reports/session/presets/expected_kpis_standard.json",
  "tolerance_json": "reports/session/presets/tolerances_standard.json",
  "output_dir": "reports/reconcile",
  "db_path": "trading_paper.db",
  "strict_reconcile": false,
  "skip_health_check": false,
  "skip_rotate": false,
  "notes": "Optional context for this trial run"
}
```

### Field Reference

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `name` | string | required | Display name for logging |
| `profile` | string | required | "default" or "uk_paper" |
| `strategy` | string | required | "ma_crossover", "rsi_momentum", etc. |
| `duration_seconds` | int | required | How long to run paper trading |
| `symbols` | list[str] | None | If unset, uses profile defaults |
| `capital` | float | 100000.0 | Starting cash |
| `expected_json` | string | None | Path to expected KPIs (for reconcile step) |
| `tolerance_json` | string | None | Path to tolerances (for reconcile step) |
| `output_dir` | string | "reports/reconcile" | Where to save session summary + reconciliation |
| `db_path` | string | None | Paper trading DB; if None, uses profile default |
| `strict_reconcile` | bool | False | Exit code 1 if drift > tolerances |
| `skip_health_check` | bool | False | Skip pre-flight health checks |
| `skip_rotate` | bool | False | Don't archive old paper DB before run |
| `notes` | string | None | Any context for this trial |

## Workflow Examples

### Example 1: Daily Health Check (Aggressive)
```bash
# Run quick 5-minute smoke test, warnings only
python main.py paper_trial --manifest configs/trial_aggressive.json

# Check reports/reconcile/paper_reconciliation.csv for any drift
# Exit code 0 even if drift found (non-blocking)
```

### Example 2: Pre-Live Validation (Conservative)
```bash
# Run 1-hour rigorous trial, must pass strict KPI gates
python main.py paper_trial --manifest configs/trial_conservative.json

# If exit code 0, all KPIs within tight tolerances → safe to promote
# If exit code 1, drift detected → investigate and retry tuning
```

### Example 3: Custom Trial (Your Manifest)
Create `configs/trial_my_experiment.json`:
```json
{
  "name": "RSI + ADX Experiment",
  "profile": "uk_paper",
  "strategy": "rsi_momentum",
  "duration_seconds": 1800,
  "symbols": ["AAPL", "MSFT"],
  "capital": 50000.0,
  "expected_json": "reports/session/presets/expected_kpis_standard.json",
  "tolerance_json": "reports/session/presets/tolerances_standard.json",
  "output_dir": "reports/rsi_experiment",
  "strict_reconcile": false,
  "skip_health_check": false,
  "skip_rotate": true,
  "notes": "Testing RSI 30/70 levels with tighter entry filters"
}
```

Then run:
```bash
python main.py paper_trial --manifest configs/trial_my_experiment.json
```

## Legacy CLI Mode (No Manifest)

If you prefer explicit flags instead of a manifest file:
```bash
python main.py paper_trial \
  --profile uk_paper \
  --strategy ma_crossover \
  --symbols MSFT AAPL NVDA \
  --paper-duration-seconds 900 \
  --expected-json reports/session/presets/expected_kpis_standard.json \
  --tolerance-json reports/session/presets/tolerances_standard.json \
  --output-dir reports/reconcile \
  --strict-reconcile
```

**Note**: Manifest mode (`--manifest`) overrides all CLI flags.

## Execution Flow

```
paper_trial --manifest manifest.json
│
├─> Load manifest.json
├─> Apply profile/strategy/symbols overrides
├─> Run health check (unless --skip-health-check)
│   └─> Exit code 2 if blocking errors found
├─> Rotate (archive) old paper DB (unless --skip-rotate)
├─> Run paper trading for duration_seconds
├─> Export session summary (fill_rate, win_rate, P&L, etc.)
├─> Run reconciliation if expected_json provided
│   └─> Compare actual vs expected KPIs
│   └─> Flag drift if > tolerances
│   └─> Exit code 1 if --strict-reconcile and drift found
└─> Exit code 0 on success
```

## Exit Codes

| Code | Meaning |
|------|---------|
| **0** | Success: All gates passed (health check, optional reconcile drift) |
| **1** | Reconciliation drift detected and `--strict-reconcile` enabled |
| **2** | Health check failed (blocking errors) |

## Creating Custom Manifests

1. Copy a preset as template:
   ```bash
   cp configs/trial_standard.json configs/trial_my_custom.json
   ```

2. Edit JSON with your settings

3. Run:
   ```bash
   python main.py paper_trial --manifest configs/trial_my_custom.json
   ```

## Preset KPI Targets

All preset expected KPIs and tolerances are under `reports/session/presets/`:

```
reports/session/presets/
├── expected_kpis_conservative.json
├── expected_kpis_standard.json
├── expected_kpis_aggressive.json
├── tolerances_conservative.json
├── tolerances_standard.json
└── tolerances_aggressive.json
```

You can reference these in custom manifests or create your own KPI JSON files.

## Tips & Best Practices

1. **Use Conservative for pre-live validation**
   - Runs longer (1 hour)
   - Higher trade count requirement (30+)
   - Tighter KPI tolerances
   - Must pass drift checks (strict_reconcile: true)

2. **Use Standard for daily health checks**
   - Quick 15-minute run
   - Moderate trade requirement (20+)
   - Warnings on drift but doesn't block CI

3. **Use Aggressive for integration tests**
   - Very fast (5 min)
   - Low trade count (12+)
   - Loose tolerances
   - Catches major breaks only

4. **Custom manifests for A/B testing**
   - Create a separate manifest for each strategy variant
   - Use different output_dir to avoid mixing results
   - Run side-by-side to compare performance

## Troubleshooting

### Manifest file not found?
```
FileNotFoundError: [Errno 2] No such file or directory: 'configs/trial_foo.json'
```
→ Check the path. Must be relative to workspace root.

### Invalid JSON in manifest?
```
json.JSONDecodeError: ...
```
→ Use a JSON validator (https://jsonlint.com) to check syntax.

### Missing required field?
```
TypeError: __init__() missing 1 required positional argument: '...'
```
→ Check that all required fields (name, profile, strategy, duration_seconds) are present.

### Drift detected during strict-reconcile?
```
Exit code 1
```
→ Review `reports/reconcile/paper_reconciliation.csv`. Check columns: drift_abs, within_tolerance, drift_flag. Adjust expected_json values or skip_rotate to preserve history.

