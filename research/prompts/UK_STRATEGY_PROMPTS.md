# UK Strategy Research Prompt Pack

Use this pack to research and implement new offline strategies for profitability with UK-first operating constraints.

## Agent Selection Rules

- **Copilot**: implementation, refactors, tests, code integration
- **Claude Opus**: policy, framework, methodology, model-risk design, evaluation standards

## Prompt Breakdown (with best agent)

| ID | Prompt Goal | Best Agent | Why |
|---|---|---|---|
| P1 ✅ | Define UK-first tradable universe and liquidity filters | Claude Opus | Research depth + market-structure framing |
| P2 ✅ | Implement reproducible data snapshot pipeline | Copilot | Concrete code + tests |
| P3 ✅ | Define leakage-safe labeling and feature spec | Claude Opus | Method quality and pitfalls |
| P4 ✅ | Implement feature/label generation modules | Copilot | Deterministic engineering tasks |
| P5 ✅ | Design walk-forward + regime validation protocol | Claude Opus | Statistical protocol design |
| P6 ✅ | Implement experiment harness + reporting | Copilot | Multi-file implementation |
| P7 ✅ | Design ML baseline stack (XGBoost/LSTM) and risk controls | Claude Opus | Model governance and safety |
| P8 ✅ | Implement model training/eval + artifact metadata | Copilot | Pipeline coding and persistence |
| P9 ✅ | Define promotion gates from research to runtime | Claude Opus | Governance and rollout logic |
| P10 ✅ | Implement strategy factory bridge into runtime registry | Copilot | Integration with existing codebase |

---

## Ready-to-Use Prompts

### P1 — UK universe definition (Claude Opus) ✅ COMPLETED 2026-02-23
**Output:** `research/specs/UK_UNIVERSE.md`

```text
You are a systematic equities researcher helping build a UK-based trading bot.
Define a UK-first tradable universe for profit-seeking strategy research.
Include:
1) Core UK symbols/baskets (FTSE 100/250, ETFs)
2) Liquidity/spread filters for offline and paper-trial viability
3) Optional non-UK expansion criteria (US/EU/global) and when to include them
4) Regime coverage requirements so results are not overfit to one market phase
5) A minimum viable universe and an expanded universe
Output as a practical specification with thresholds and trade-offs.
```

### P2 — Snapshot pipeline implementation (Copilot) ✅ ANSWERED 2026-02-23

```text
Implement a reproducible offline snapshot pipeline under research/data/:
- Write snapshot metadata JSON (source universe, date range, timezone, hash)
- Store data in parquet/csv with deterministic naming
- Add a loader utility that validates hash + schema
- Add tests for reproducibility and corruption detection
Keep implementation isolated from runtime trading paths.
```

**Answer (implementation specification):**
- Create `research/data/snapshots/store.py` with `SnapshotStore`:
	- `create_snapshot(df, *, universe_id, timeframe, start, end, tz="UTC") -> SnapshotManifest`
	- `load_snapshot(snapshot_id) -> pd.DataFrame`
	- `validate_snapshot(snapshot_id) -> ValidationResult`
- File layout:
	- `research/data/snapshots/<snapshot_id>/bars.parquet`
	- `research/data/snapshots/<snapshot_id>/manifest.json`
- Snapshot ID convention:
	- `sha256(universe_id|timeframe|start|end|row_count|first_ts|last_ts|schema_signature)`
- `manifest.json` fields:
	- `snapshot_id`, `created_at_utc`, `universe_id`, `timeframe`, `start_utc`, `end_utc`, `row_count`, `columns`, `dtypes`, `data_hash_sha256`, `code_version`
- Validation logic:
	- schema exact-match check
	- recompute file hash and compare to manifest
	- timestamp monotonicity + duplicate timestamp-symbol check
- Tests:
	- deterministic ID for same input
	- tampered parquet fails hash validation
	- schema mismatch fails validation with clear error

### P3 — Feature/label specification (Claude Opus) ✅ COMPLETED 2026-02-23
**Output:** `research/specs/FEATURE_LABEL_SPEC.md`

```text
Design leakage-safe feature and label definitions for a UK-first equities strategy lab.
Include:
- horizon definitions for classification/regression
- feature families (price, volume, volatility, regime, cross-sectional)
- leakage traps and mitigation rules
- class imbalance handling
- validation split strategy compatible with walk-forward testing
Output in implementation-ready schema/table form.
```

### P4 — Feature/label modules (Copilot) ✅ ANSWERED 2026-02-23

```text
Implement research data feature/label modules from the agreed spec:
- features.py and labels.py
- deterministic transforms with seed/config control
- unit tests for shape, null handling, and timestamp alignment
- strict checks that labels use only future returns and features use only past/current info
```

**Answer (implementation specification):**
- Create modules:
	- `research/data/features/features.py`
	- `research/data/features/labels.py`
	- `research/data/features/contracts.py`
- Feature contract:
	- all features indexed by `(symbol, timestamp_utc)`
	- no forward shift allowed in feature transforms
	- `feature_version` string stored alongside outputs
- Label contract:
	- binary label: `y_5d = 1 if close.shift(-5) > close else 0`
	- regression label optional: `fwd_ret_5d = close.shift(-5)/close - 1`
	- rows with insufficient forward horizon dropped after label creation
- Leakage checks:
	- enforce `max(feature_ts) <= label_origin_ts`
	- unit tests asserting no `shift(-k)` usage in features (except in labels)
- Tests:
	- shape and null policy checks
	- timestamp alignment checks per symbol
	- deterministic output with fixed seed/config

### P5 — Validation protocol (Claude Opus) ✅ COMPLETED 2026-02-23
**Output:** `research/specs/VALIDATION_PROTOCOL.md`

```text
Design a walk-forward + regime-split validation protocol for strategy research.
Include:
- train/validation/test windowing schedule
- confidence reporting requirements
- pass/fail thresholds for promotion to paper trial
- overfitting diagnostics and rejection criteria
Provide a concise protocol that can be automated.
```

### P6 — Experiment harness (Copilot) ✅ ANSWERED 2026-02-23

```text
Implement an experiment harness in research/experiments/ that:
- runs walk-forward folds
- records per-fold metrics and aggregate summary
- saves run metadata + config + seed + dataset snapshot ID
- emits a machine-readable report for promotion checks
Add focused tests.
```

**Answer (implementation specification):**
- Create `research/experiments/harness.py`:
	- `run_experiment(config: ExperimentConfig) -> ExperimentReport`
	- fold runner using walk-forward windows from `VALIDATION_PROTOCOL.md`
- Output files per run:
	- `research/experiments/runs/<run_id>/config.json`
	- `research/experiments/runs/<run_id>/fold_metrics.csv`
	- `research/experiments/runs/<run_id>/report.json`
- Required report fields:
	- `run_id`, `snapshot_id`, `feature_version`, `label_version`, `seed`, `folds`, `aggregate_metrics`, `pass_fail`
- Aggregate metrics minimum:
	- win_rate mean/std, precision, recall, pnl proxy, max_drawdown proxy, fold degradation stats
- Tests:
	- report schema validation
	- reproducibility check with fixed seed
	- pass/fail threshold logic test

### P7 — ML baseline + risk controls (Claude Opus) ✅ COMPLETED 2026-02-23
**Output:** `research/specs/ML_BASELINE_SPEC.md`

```text
Define a practical ML baseline stack (e.g., XGBoost + optional LSTM) for UK-first strategy research.
Include:
- model choice rationale
- calibration and thresholding policy
- feature stability/drift monitoring requirements
- fail-safe fallback behavior when model confidence degrades
- what evidence is required before candidate promotion
```

### P8 — Training/eval pipeline (Copilot) ✅ ANSWERED 2026-02-23

```text
Implement model training/evaluation pipeline in research/models/:
- train and evaluate XGBoost baseline
- optional LSTM trainer scaffold
- store model artifact + metadata + metrics
- load artifacts for offline scoring
- add tests for artifact integrity and version compatibility
```

**Answer (implementation specification):**
- Create:
	- `research/models/train_xgboost.py`
	- `research/models/train_lstm.py` (scaffold)
	- `research/models/artifacts.py`
- Artifact layout:
	- `research/models/artifacts/<model_id>/model.bin` (or `.pt`)
	- `research/models/artifacts/<model_id>/metadata.json`
- Metadata required:
	- `model_id`, `model_type`, `snapshot_id`, `feature_version`, `label_version`, `train_window`, `val_window`, `metrics`, `artifact_hash`, `created_at_utc`
- Integrity rules:
	- load blocked if artifact hash mismatch
	- load blocked if required feature version differs
- Tests:
	- save/load round-trip
	- hash mismatch rejection
	- metadata compatibility rejection path

### P9 — Promotion policy (Claude Opus) ✅ COMPLETED 2026-02-23
**Output:** `research/specs/RESEARCH_PROMOTION_POLICY.md`

```text
Draft a promotion policy for research-generated strategies entering runtime.
Policy must include:
- required evidence bundle (data snapshot, reproducibility metadata, OOS metrics)
- mandatory paper-trial thresholds
- rollback conditions and monitoring triggers
- explicit no-go criteria
Format for direct inclusion in project docs.
```

### P10 — Runtime strategy bridge (Copilot) ✅ ANSWERED 2026-02-23

```text
Implement a strategy-factory bridge from research outputs to runtime-compatible strategy registration:
- map candidate config/model to runtime strategy interface
- enforce mandatory metadata validation
- reject candidates missing required promotion evidence
- add tests for happy path and policy rejections
Keep runtime invariants intact.
```

**Answer (implementation specification):**
- Create `research/bridge/strategy_factory.py`:
	- `build_runtime_candidate(candidate_bundle) -> RuntimeStrategySpec`
	- `validate_candidate_bundle(bundle) -> ValidationResult`
- Bundle must include:
	- experiment report (`pass_fail=true`)
	- artifact metadata + hash
	- promotion evidence checklist entries required by `RESEARCH_PROMOTION_POLICY.md`
- Runtime integration:
	- register candidate through existing registry with `status=experimental`
	- block direct promotion to live
	- keep `RiskManager.approve_signal()` as sole signal→order path
- Rejection reasons (explicit):
	- missing evidence fields
	- failed thresholds
	- hash mismatch
	- incompatible feature/model version
- Tests:
	- valid candidate accepted and registered
	- each rejection reason covered
	- regression test ensuring runtime mode guards remain unchanged

---

## Note on completion markers

`✅ ANSWERED` in this file means the prompt now has a concrete implementation answer/spec.
It does **not** mean code implementation is complete. Track implementation status in:
- `research/tickets/UK_RESEARCH_TICKETS.md`
- `IMPLEMENTATION_BACKLOG.md`
