# UK Operations Runbook

End-to-end operational guide for UK-based paper trading and UK tax export workflow.

---

## 1) Preconditions

- Python environment installed and dependencies available:
  - `python -m pip install -r requirements.txt`
- Interactive Brokers TWS or IB Gateway running locally.
- IBKR is set to **paper** account mode (`DU...`) for sandbox runs.
- You are in project root:
  - `C:\Users\rando\Projects\trading-bot`
- Database isolation env vars are configured (defaults now provided in `.env`):
  - `DATABASE_URL_PAPER=sqlite:///trading_paper.db`
  - `DATABASE_URL_LIVE=sqlite:///trading_live.db`
  - `DATABASE_URL_TEST=sqlite:///trading_test.db`
  - `STRICT_DB_ISOLATION=true`

---

## 2) Validate Build Health

Run tests before any live paper session:

```bash
python -m pytest tests/ -v
```

Expected: full pass.

Run UK pre-flight checks before starting sessions:

```bash
python main.py uk_health_check --profile uk_paper --strict-health
```

Optional data connectivity validation:

```bash
python main.py uk_health_check --profile uk_paper --with-data-check --strict-health
```

Machine-readable JSON output (for schedulers/alerting):

```bash
python main.py uk_health_check --profile uk_paper --health-json --strict-health
```

---

## 3) Start UK Paper Profile

Run with UK profile defaults (IBKR + UK symbols + GBP base):

```bash
python main.py paper --profile uk_paper --strategy ma_crossover
```

UK profile currently applies:
- Broker: `ibkr`
- IBKR paper port: `7497`
- Market timezone: `Europe/London`
- Symbols: `HSBA.L VOD.L BP.L BARC.L SHEL.L`
- Base currency: `GBP`
- FX seed rate: `USD_GBP=0.79`
- Market-hours gating: enabled

---

## 4) Operational Safety Checks

At startup, verify logs indicate:
- IBKR account detected as paper (`DU...`)
- Pre-warm completed (or clear warnings per symbol)
- Paper trading loop started

The runtime guardrails will block:
- paper mode + live IBKR account mismatch
- live mode + paper IBKR account mismatch

---

## 5) Optional Runtime Variants

Disable market-hours gating (debug only):

```bash
python main.py paper --profile uk_paper --no-market-hours
```

Override symbols while still using UK profile:

```bash
python main.py paper --profile uk_paper --symbols HSBA.L VOD.L BARC.L
```

---

## 6) Audit and Tax Export

Paper/live loop writes audit events into `trading.db` (signals, orders, fills, session lifecycle, errors).

Generate UK tax-oriented CSVs:

```bash
python main.py uk_tax_export --profile uk_paper --db-path trading.db --output-dir reports/uk_tax
```

Generated files:
- `reports/uk_tax/trade_ledger.csv`
- `reports/uk_tax/realized_gains.csv`
- `reports/uk_tax/fx_notes.csv`

Generate paper session KPI summary (JSON + CSV):

```bash
python main.py paper_session_summary --profile uk_paper --db-path trading.db --output-dir reports/session
```

Generated files:
- `reports/session/paper_session_summary.json`
- `reports/session/paper_session_summary.csv`

Run paper KPI reconciliation against expected targets:

```bash
python main.py paper_reconcile --profile uk_paper --db-path trading.db --expected-json reports/session/expected_kpis.json --output-dir reports/reconcile
```

Fail CI/automation when drift flags are detected:

```bash
python main.py paper_reconcile --profile uk_paper --db-path trading.db --expected-json reports/session/expected_kpis.json --output-dir reports/reconcile --strict-reconcile
```

Optional custom tolerance overrides:

```bash
python main.py paper_reconcile --profile uk_paper --db-path trading.db --expected-json reports/session/expected_kpis.json --tolerance-json reports/session/tolerances.json --output-dir reports/reconcile
```

Preset KPI profiles (recommended):

```bash
# Conservative
python main.py paper_reconcile --profile uk_paper --db-path trading.db --expected-json reports/session/presets/expected_kpis_conservative.json --tolerance-json reports/session/presets/tolerances_conservative.json --output-dir reports/reconcile --strict-reconcile

# Standard (default baseline)
python main.py paper_reconcile --profile uk_paper --db-path trading.db --expected-json reports/session/presets/expected_kpis_standard.json --tolerance-json reports/session/presets/tolerances_standard.json --output-dir reports/reconcile --strict-reconcile

# Aggressive
python main.py paper_reconcile --profile uk_paper --db-path trading.db --expected-json reports/session/presets/expected_kpis_aggressive.json --tolerance-json reports/session/presets/tolerances_aggressive.json --output-dir reports/reconcile --strict-reconcile
```

Generated files:
- `reports/reconcile/paper_reconciliation.json`
- `reports/reconcile/paper_reconciliation.csv`

### Simplified: Trial Manifests

Instead of long CLI arguments, use pre-configured manifest JSON files (recommended for repeatable checks):

**Standard (15-min baseline health check):**
```bash
python main.py paper_trial --manifest configs/trial_standard.json
```

**Conservative (1-hour pre-live validation):**
```bash
python main.py paper_trial --manifest configs/trial_conservative.json
```

**Quick smoke test (5-min integration test):**
```bash
python main.py paper_trial --manifest configs/trial_aggressive.json
```

Notes on trials:
- Runs UK health check first (fails fast on blocking errors).
- Runs symbol-universe data preflight policy before trial stream startup.
- Rotates paper DB by default before trial start.
- Runs paper loop for configured duration, then exports summary and reconciliation.
- Use `--skip-health-check` or `--skip-rotate` only for debugging.
- See [TRIAL_MANIFEST.md](TRIAL_MANIFEST.md) for full manifest documentation and custom manifest creation.

Symbol-universe policy controls (env vars):
- Strict mode (default block on low availability):
  - `SYMBOL_UNIVERSE_STRICT_MODE=true`
  - `SYMBOL_UNIVERSE_MIN_AVAILABILITY_RATIO=0.80`
  - `SYMBOL_UNIVERSE_MIN_BARS_PER_SYMBOL=100`
  - `SYMBOL_UNIVERSE_PREFLIGHT_PERIOD=5d`
  - `SYMBOL_UNIVERSE_PREFLIGHT_INTERVAL=1m`
- Optional deterministic remediation mode (continue with healthy subset):
  - `SYMBOL_UNIVERSE_REMEDIATION_ENABLED=true`
  - `SYMBOL_UNIVERSE_REMEDIATION_MIN_SYMBOLS=3`
  - `SYMBOL_UNIVERSE_REMEDIATION_TARGET_SYMBOLS=0` (0 = keep all healthy symbols)

When remediation adjusts the active universe, runtime emits audit event `SYMBOL_UNIVERSE_REMEDIATED` with before/after details.

### Legacy: Long CLI Format

If you prefer explicit flags instead of manifest JSON:

```bash
python main.py paper_trial --profile uk_paper --paper-duration-seconds 900 --expected-json reports/session/presets/expected_kpis_standard.json --tolerance-json reports/session/presets/tolerances_standard.json --output-dir reports/reconcile --strict-reconcile
```

---

## 7) Interpreting Export Files

### `trade_ledger.csv`
Contains per-fill rows including:
- timestamp, symbol, side, qty
- `price_reference`, `price`, `slippage_pct_vs_signal`
- `fee`, `currency`
- base-currency normalized gross/fee columns

### `realized_gains.csv`
Contains FIFO-matched realized gains per sell event:
- matched quantity
- proceeds (base currency)
- cost basis (base currency)
- realized gain (base currency)

### `fx_notes.csv`
Lists FX pairs used during conversion and configured rates.

---

## 8) Troubleshooting

### IBKR connection fails
- Confirm TWS/Gateway is running.
- Confirm API access is enabled.
- Confirm host/port/client ID values (`127.0.0.1:7497` for paper default).

### No data for UK symbol
- Verify Yahoo/IBKR symbol format uses `.L` suffix where needed.
- Try a short manual backtest fetch first:
  - `python main.py backtest --symbols HSBA.L --start 2024-01-01 --end 2024-12-31`

### Tax export missing trades
- Ensure trading loop wrote `ORDER_FILLED`/`FILL`/`TRADE` events into `trading.db`.
- Confirm `--db-path` points to the active runtime DB.

---

## 9) Recommended Routine

1. `python -m pytest tests/ -v`
2. `python main.py uk_health_check --profile uk_paper --strict-health`
3. `python main.py paper --profile uk_paper --strategy <strategy>`
4. Let session run for target window.
5. `python main.py uk_tax_export --profile uk_paper --db-path trading.db --output-dir reports/uk_tax`
6. `python main.py paper_session_summary --profile uk_paper --db-path trading.db --output-dir reports/session`
7. `python main.py paper_reconcile --profile uk_paper --db-path trading.db --expected-json reports/session/expected_kpis.json --output-dir reports/reconcile --strict-reconcile`
8. Archive `reports/uk_tax`, `reports/session`, and `reports/reconcile` with run date and strategy metadata.

---

## 10) Git Hygiene (Operator Quick Rules)

Use non-destructive stash restore by category to avoid reintroducing runtime noise:
- Code only: `git checkout 'stash@{0}' -- src tests config scripts`
- Docs only: `git checkout 'stash@{0}' -- *.md docs`
- Runtime artifacts only (only when explicitly needed): `git checkout 'stash@{0}' -- reports`

Keep commit boundaries strict:
- Commit A: Git hygiene and policy files only (`.gitignore`, CI workflow, runbook updates)
- Commit B: application/runtime code changes only
- Commit C: docs-only updates (LPDD/session logs/backlog)

Do not commit local secret/runtime files:
- `.env` (keep `.env.example` tracked)
- local DB/runtime artifacts (`*.db`, `*.sqlite`, `*.sqlite3`)

Tip: Replace `expected_kpis.json`/`tolerances.json` with one of the files in `reports/session/presets/` to choose conservative, standard, or aggressive drift policy.
Tip: For repeatable ops, replace steps 3-7 with a single `paper_trial` run.

---

## 9b) Manual-Execution Scripts for Live Testing Windows

These scripts require **manual/operator execution** (credentials, market-window timing,
or explicit sign-off). Do not run unattended as part of autonomous agent workflows.

| Script | Purpose | Manual Requirement |
|---|---|---|
| `run_step1a_market.ps1` | Execute in-window Step 1A market run | Must be run during 08:00–16:00 UTC with IBKR paper session active |
| `run_step1a_market_if_window.ps1` | Guarded market-window runner | Operator must verify scheduler timing and inspect skip/pass outputs |
| `run_step1a_session.ps1` | End-to-end Step 1A session sequence | Requires live IBKR connectivity and human review of generated artifacts |
| `run_step1a_burnin.ps1` | Multi-run burn-in orchestration | Requires sequential in-window supervision and acceptance checks |
| `append_step1a_evidence.ps1` | Append burn-in evidence to backlog/logs | Requires operator confirmation that artifact values are correct |

Operational note:
- Prefer `python main.py ...` commands for reproducible audit trails.
- Use PowerShell wrappers above only when running MO-2/Step 1A operational closure tasks.
- Safety lock: these Step 1A wrapper scripts now fail-fast unless `Profile=uk_paper`.

### 9c) Container Mode (IBKR-DKR-05)

Use container mode only for reproducible orchestration wrappers and report processing.
IBKR TWS/Gateway remains an operator-managed endpoint and must be reachable from the container network.

Startup checklist:
- Start TWS/IB Gateway in paper mode (`DU...`) on the host.
- Ensure container can resolve/connect to `IBKR_HOST` + `IBKR_PORT`.
- Run `python main.py uk_health_check --profile uk_paper --strict-health` before session commands.

Verification checkpoints:
- `broker_provider` check reports IBKR for `uk_paper`.
- Step1A/MO-2 outputs include endpoint profile tag (`ibkr:<profile>:<mode>:<host>:<port>`).
- Latest burn-in pointer exists: `reports/uk_tax/step1a_burnin/step1a_burnin_latest.json`.

Recovery signatures:
- `client id is already in use` → use auto-client wrapper path (already default in Step1A market wrapper).
- `Connection refused` / timeout → verify host/port exposure and TWS API settings.
- `symbol_data_preflight_failed` → adjust run window or symbol availability threshold per policy.

Security notes:
- Do not bake `.env` into container images.
- Mount report/output directories as writable volumes; keep credentials local/operator-managed.
- Keep `coinbase_sandbox` and `binance_testnet` true unless explicitly gated closed.

### 9d) Report-Schema Compatibility Adapter (IBMCP-05)

Read-only adapter utility: `src/reporting/report_schema_adapter.py`

Operator usefulness:
- Normalizes key report outputs without broker/API calls.
- Exposes stable resources for tooling integration:
  - `step1a_latest`
  - `paper_session_summary`
  - `mo2_latest`

Example usage:

```python
from src.reporting.report_schema_adapter import ReportSchemaAdapter

adapter = ReportSchemaAdapter(".")
resources = adapter.list_resources()
payload = adapter.get_resource("step1a_latest")
```

### One-Command MO-2 Orchestrator (Recommended)

Run the full MO-2 sequence end-to-end (3 in-window runs) with explicit guardrails
and timestamped orchestration artifacts:

```powershell
./scripts/run_mo2_end_to_end.ps1 -Runs 3 -PaperDurationSeconds 1800 -MinFilledOrders 5 -MinSymbolDataAvailabilityRatio 0.80 -PreflightMinBarsPerSymbol 100 -AppendBacklogEvidence
```

What it enforces:
- profile lock: `uk_paper` only
- must start within 08:00–16:00 UTC window
- sequential run execution (no parallel overlap)
- optional kill-switch clear before each run
- symbol-data preflight gate before each run (`reason=symbol_data_preflight_failed` if ratio below threshold)

Preflight controls:
- `-MinSymbolDataAvailabilityRatio` (default `0.80`): required fraction of configured symbols with usable bars
- `-PreflightMinBarsPerSymbol` (default `100`): minimum bar count for a symbol to be considered available
- `-PreflightPeriod` (default `5d`) and `-PreflightInterval` (default `1m`): fetch window for availability check
- `-SkipSymbolAvailabilityPreflight`: disables the gate (operator override; not recommended for MO-2 sign-off)

What it writes:
- session log: `reports/uk_tax/mo2_orchestrator/session_<timestamp>/mo2_orchestrator.log`
- orchestration report: `reports/uk_tax/mo2_orchestrator/session_<timestamp>/mo2_orchestrator_report.json`
- underlying burn-in latest pointer: `reports/uk_tax/step1a_burnin/step1a_burnin_latest.json`
- per-run preflight report: `reports/uk_tax/step1a_burnin/session_<timestamp>/run_<n>/00_symbol_data_preflight.json`

---

## 10) Paper DB Rotation (Session Isolation)

Archive (move) current paper DB into dated archive path:

```bash
python main.py rotate_paper_db --profile uk_paper --archive-dir archives/db
```

Enable automatic rotation at paper session start:

```bash
python main.py paper --profile uk_paper --auto-rotate-paper-db
```

Disable auto-rotation explicitly (overrides env default):

```bash
python main.py paper --profile uk_paper --no-auto-rotate-paper-db
```

Keep current DB and archive a copy instead:

```bash
python main.py rotate_paper_db --profile uk_paper --archive-dir archives/db --keep-original
```

Force deterministic archive suffix (useful for scripted runs):

```bash
python main.py rotate_paper_db --profile uk_paper --archive-dir archives/db --rotate-suffix 20260223_120000
```
