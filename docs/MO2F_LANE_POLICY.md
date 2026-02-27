# MO-2 / MO-2F Lane Policy

## Purpose

Define admissibility boundaries between qualifying MO-2 signoff evidence and functional-only MO-2F evidence.

## Lane Taxonomy

| Lane | Value | Window | Signoff Eligible | Promotion Eligible |
|---|---|---|---|---|
| Qualifying | `qualifying` | 08:00–16:00 UTC (Mon–Fri) | Yes | Yes |
| Functional-only | `functional_only` | Any time | No | No |

## Admissibility Matrix

| Dependency Class | `qualifying` | `functional_only` |
|---|---:|---:|
| MO-2 signoff | ✅ | ❌ |
| Live promotion / Gate B evidence | ✅ | ❌ |
| Functional dependency validation | ✅ | ✅ |
| Script/artifact regression checks | ✅ | ✅ |
| Reconciliation-path verification | ✅ | ✅ |

## Artifact Labeling (Required)

Step1A burn-in reports must include:
- `run_objective_profile`: `smoke|orchestration|reconcile|qualifying`
- `evidence_lane`: `qualifying|functional_only`
- `lane_reason`: derivation reason (`qualifying_conditions_met|objective_profile_forces_functional|non_qualifying_test_mode|out_of_window|short_duration|command_failed`)

Both session-level and per-run outputs should carry lane metadata.

## Lane Derivation Rules

A run may be `qualifying` only when all are true:
1. `run_objective_profile == "qualifying"`
2. `non_qualifying_test_mode == false`
3. in-window start condition is met
4. `paper_duration_seconds >= 1800`

Otherwise lane must be `functional_only`.

## Duration Profiles

| Profile | Min Duration | Default Duration | Lane | Min Filled Orders |
|---|---:|---:|---|---:|
| `smoke` | 30s | 60s | `functional_only` | 0 |
| `orchestration` | 120s | 300s | `functional_only` | 0 |
| `reconcile` | 300s | 900s | `functional_only` | 1 (default) |
| `qualifying` | 1800s | 1800s | `qualifying` | 5 (default) |

## Hard Guardrails

- Runs shorter than 1800s can never set `signoff_ready=true`.
- `smoke`, `orchestration`, and `reconcile` profiles must always be `functional_only`.
- Functional-only evidence is permanently inadmissible for MO-2 signoff and promotion gate substitution.
- Lane classification is immutable once report artifacts are written.
