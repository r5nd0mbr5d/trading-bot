# UK Research Implementation Tickets (Initial)

Execution order for the new UK-first strategy R&D track.

## Ticket R1 — Reproducible Snapshot Pipeline

**Owner agent:** Copilot  
**Status:** ✅ COMPLETED 2026-02-23
**Goal:** deterministic offline dataset snapshots for research reproducibility.

### Deliverables
- `research/data/snapshots.py` snapshot writer + loader
- metadata file with snapshot hash and schema summary
- loader validation (schema/hash)
- focused tests

### Acceptance
- same input config creates same hash
- tampered snapshot fails validation
- tests pass

**Evidence**
- `tests/test_research_snapshots.py` (2 tests)
- `python -m pytest tests/test_research_snapshots.py -q` → pass

---

## Ticket R2 — Walk-Forward Experiment Harness

**Owner agent:** Copilot  
**Status:** ✅ COMPLETED 2026-02-23
**Goal:** consistent offline evaluation with aggregate metrics and fold-level evidence.

### Deliverables
- run orchestrator in `research/experiments/harness.py`
- per-fold metrics + aggregate report output
- run metadata (snapshot ID, feature set, seed, config)
- focused tests

### Acceptance
- multiple folds run end-to-end
- report contains fold + aggregate metrics
- report is machine-readable for promotion checks

**Evidence**
- `tests/test_research_harness.py` (2 tests)
- `python -m pytest tests/test_research_harness.py -q` → pass

---

## Ticket R3 — Strategy Factory Bridge

**Owner agent:** Copilot  
**Status:** ✅ COMPLETED 2026-02-23
**Goal:** connect validated research candidates to runtime strategy registration safely.

### Deliverables
- candidate-to-runtime mapping module (`research/bridge/strategy_bridge.py`)
- mandatory evidence/metadata validator
- rejection path for incomplete candidate bundles
- focused tests

### Acceptance
- valid candidate can be registered
- invalid/missing evidence is rejected with clear reason
- runtime invariants remain intact

**Evidence**
- `tests/test_research_strategy_bridge.py` (3 tests)
- `python -m pytest tests/test_research_strategy_bridge.py -q` → pass

---

## Ticket R4 — Methodology + Governance Specs ✅ COMPLETED 2026-02-23

**Owner agent:** Claude Opus
**Goal:** define method and policy before scaling experiment throughput.

### Deliverables
- ✅ feature/label leakage-safe spec → `research/specs/FEATURE_LABEL_SPEC.md`
- ✅ walk-forward protocol spec → `research/specs/VALIDATION_PROTOCOL.md`
- ✅ promotion and rollback policy spec → `research/specs/RESEARCH_PROMOTION_POLICY.md`

### Acceptance
- ✅ specs are implementation-ready and testable
- ✅ each rule has objective pass/fail criteria

---

## Recommended Sequence

1. R4 (specs) in parallel with R1 (snapshot pipeline)
2. R2 (experiment harness) after R1 metadata is stable
3. R3 (runtime bridge) after R2 report schema is finalized
