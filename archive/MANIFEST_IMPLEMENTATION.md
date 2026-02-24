# Trial Manifest Implementation — Summary

## Overview

Trial Manifest framework enables **configuration-driven paper trading validation**. Instead of typing long CLI arguments, you define all settings once in JSON and invoke them with a single `--manifest` flag.

## What Was Built

### Core Components

1. **`src/trial/manifest.py`** — Dataclass + JSON serialization
   - `TrialManifest` dataclass with 14 configurable fields
   - `from_json()` loader for reading manifest files
   - `to_json()` saver for exporting configurations

2. **Three Preset Manifests** under `configs/`
   - `trial_conservative.json` — 1 hour, strict KPI gates, 30+ trades minimum
   - `trial_standard.json` — 15 minutes, baseline validation, 20+ trades  
   - `trial_aggressive.json` — 5 minutes, quick smoke test, 12+ trades

3. **CLI Integration** in `main.py`
   - New `--manifest` flag for `paper_trial` mode
   - Manifest-based override of profile/strategy/symbols/capital
   - Fallback to legacy CLI args if no manifest provided

4. **9 New Tests** (163 total, up from 154)
   - 4 tests in `test_trial_manifest.py` — load/save/defaults/roundtrip
   - 5 tests in `test_main_paper_trial_manifest.py` — CLI integration, validation, error cases

5. **Comprehensive Documentation**
   - `TRIAL_MANIFEST.md` — 350-line guide with examples, troubleshooting, best practices
   - Updated `UK_OPERATIONS.md` with manifest quick-start examples
   - Updated `PROJECT_STATUS.md` with new feature and test counts
   - Updated `DOCUMENTATION_INDEX.md` with manifest guide link

## Usage Examples

### Simplified One-Liner Commands

```bash
# Conservative (pre-live): 1 hour, strict KPI gates
python main.py paper_trial --manifest configs/trial_conservative.json

# Standard (daily check): 15 minutes, baseline validation
python main.py paper_trial --manifest configs/trial_standard.json

# Aggressive (smoke test): 5 minutes, integration test
python main.py paper_trial --manifest configs/trial_aggressive.json
```

### Custom Manifest Example

Create `configs/trial_my_strategy.json`:
```json
{
  "name": "RSI Momentum A/B Test",
  "profile": "uk_paper",
  "strategy": "rsi_momentum",
  "duration_seconds": 1800,
  "symbols": ["AAPL", "MSFT"],
  "capital": 75000.0,
  "expected_json": "reports/session/presets/expected_kpis_standard.json",
  "tolerance_json": "reports/session/presets/tolerances_standard.json",
  "output_dir": "reports/rsi_test",
  "strict_reconcile": false,
  "skip_health_check": false,
  "skip_rotate": false,
  "notes": "Testing RSI 30/70 with tighter entries"
}
```

Then run:
```bash
python main.py paper_trial --manifest configs/trial_my_strategy.json
```

## Manifest Field Reference

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `name` | string | required | Display name for logging |
| `profile` | string | required | "default" or "uk_paper" |
| `strategy` | string | required | Strategy name (ma_crossover, rsi_momentum, etc.) |
| `duration_seconds` | int | required | How long to run paper trading |
| `symbols` | list[str] | None | If unset, uses profile defaults |
| `capital` | float | 100000 | Starting cash |
| `expected_json` | string | None | Path to expected KPIs JSON |
| `tolerance_json` | string | None | Path to tolerance JSON |
| `output_dir` | string | "reports/reconcile" | Output directory for results |
| `db_path` | string | None | Paper trading DB path |
| `strict_reconcile` | bool | False | Exit code 1 if drift detected |
| `skip_health_check` | bool | False | Skip pre-flight checks |
| `skip_rotate` | bool | False | Don't rotate paper DB before run |
| `notes` | string | None | Optional context/comments |

## Execution Flow

```
paper_trial --manifest manifest.json
├─> Load manifest.json
├─> Apply overrides (profile, strategy, symbols, capital)
├─> Health check (unless skip_health_check)
│   └─> Exit 2 if errors found
├─> Rotate DB (unless skip_rotate)
├─> Run paper trading for duration_seconds
├─> Export session summary (KPIs)
├─> Reconcile (if expected_json provided)
│   └─> Compare actual vs expected
│   └─> Exit 1 if drift and strict_reconcile
└─> Exit 0 on success
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Reconciliation drift detected (strict_reconcile=true) |
| 2 | Health check failed (blocking errors) |

## Test Coverage

### New Tests (9 total)

**test_trial_manifest.py** (4 tests)
- `test_manifest_from_json` — Load from file
- `test_manifest_to_json` — Save to file
- `test_manifest_defaults` — Default values for optional fields
- `test_manifest_roundtrip` — Save and load preserves all fields

**test_main_paper_trial_manifest.py** (5 tests)
- `test_manifest_cli_loads_config` — CLI loads manifest correctly
- `test_manifest_cli_override_settings` — Manifest overrides CLI args
- `test_manifest_missing_required_field` — TypeError on missing required fields
- `test_manifest_json_not_found` — FileNotFoundError on missing file
- `test_manifest_format_validation` — JSONDecodeError on invalid JSON

All 163 tests pass (100% pass rate).

## Key Design Decisions

1. **Manifest as Config Format** — Single source of truth for trial settings, not scattered CLI args
2. **JSON over YAML** — Built-in Python support, no extra dependencies
3. **Preset Profiles** — Three pre-configured scenarios for common use cases
4. **Backwards Compatible** — Legacy CLI mode still works; manifest is optional enhancement
5. **Strict Validation** — Manifest must include required fields; no silent defaults
6. **Graceful Override** — Manifest fields override CLI defaults without conflicts

## Benefits

1. **Reproducibility** — Save a manifest, run it anytime with identical settings
2. **Less Typing** — Simple `--manifest path` vs long multi-flag commands
3. **A/B Testing** — Create separate manifests for different strategy variants
4. **Documentation** — Notes field explains why a config was created
5. **CI/Automation** — Manifests enable scripted trial runs with predictable inputs/outputs
6. **Onboarding** — New team members can see preset examples immediately

## Integration with Existing Features

- **Compatible with UK Profile** — All presets use `uk_paper` profile
- **Works with KPI Presets** — Manifests reference expected_kpis and tolerances JSON files
- **Integrates with Health Check** — Pre-trial validation gate works unchanged
- **DB Rotation Works** — Paper DB archive happens before trial as expected
- **Audit Trail Preserved** — All events logged to audit table as normal
- **Reconciliation Reports** — Standard JSON/CSV exports generated after trial

## Files Created/Modified

### New Files
- `src/trial/manifest.py` — Manifest dataclass + JSON I/O
- `src/trial/__init__.py` — Package exports
- `configs/trial_conservative.json` — Conservative preset
- `configs/trial_standard.json` — Standard preset
- `configs/trial_aggressive.json` — Aggressive preset
- `tests/test_trial_manifest.py` — 4 manifest tests
- `tests/test_main_paper_trial_manifest.py` — 5 CLI integration tests
- `TRIAL_MANIFEST.md` — User guide

### Modified Files
- `main.py` — Added manifest import, --manifest flag, CLI handler
- `PROJECT_STATUS.md` — Updated test count to 163, added manifest feature
- `UK_OPERATIONS.md` — Added manifest examples section
- `DOCUMENTATION_INDEX.md` — Added TRIAL_MANIFEST.md reference

## Next Steps (Optional)

1. **Manifest Versioning** — Add `version` field to support future schema changes
2. **Multi-Strategy Scheduling** — Manifest array to run series of trials
3. **Manifest Repository** — Central store of tested configs with performance annotations
4. **Email Alerts** — Manifest field to specify recipient for trial result emails
5. **Dashboard Integration** — Extract trial metrics to feed operational dashboards

## Testing & Validation

All code is tested and working:
- ✅ Manifest loading from JSON (all three presets)
- ✅ Manifest saving to JSON with roundtrip preservation
- ✅ Default values for optional fields
- ✅ CLI --manifest flag integration
- ✅ Override behavior (manifest > CLI args > defaults)
- ✅ Error handling (missing file, invalid JSON, required fields)
- ✅ 163 total tests passing (100% pass rate)

## Quick Start

```bash
# Run a preset trial
python main.py paper_trial --manifest configs/trial_standard.json

# Create a custom manifest
cp configs/trial_standard.json configs/trial_my_test.json
# Edit trial_my_test.json with your settings

# Run your custom manifest
python main.py paper_trial --manifest configs/trial_my_test.json

# Check results
cat reports/reconcile/paper_reconciliation.csv
```

