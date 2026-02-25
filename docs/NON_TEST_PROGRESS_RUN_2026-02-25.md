# Non-Test Progress Run — 2026-02-25

## Selected Item

- **Step 72** — UK paper symbol-universe reliability hardening

## Why selected

- Highest-priority actionable backlog item outside active MO-2 operations.
- Directly addresses recurring `symbol_data_preflight_failed` outcomes without requiring live-run intervention.

## Ready-to-Start Checklist

1. **Add config controls in `config/settings.py`**
   - Add `SymbolUniverseHealthConfig` (or equivalent nested config) with fields:
     - `enabled: bool = True`
     - `strict_mode: bool = True`
     - `min_healthy_ratio: float = 0.8`
     - `min_bars_per_symbol: int = 100`
     - `period: str = "5d"`
     - `interval: str = "1m"`
     - `fallback_min_symbols: int = 1`
     - `fallback_max_symbols: int = 5`
   - Keep defaults aligned with current preflight gate.

2. **Create symbol-health helper in `src/data/symbol_health.py`**
   - Add dataclasses/functions:
     - `SymbolHealthResult`
     - `evaluate_symbol_universe_health(settings: Settings) -> list[SymbolHealthResult]`
     - `select_fallback_symbols(results, *, min_symbols, max_symbols) -> list[str]`
     - `summarize_health(results) -> dict`
   - Reuse `MarketDataFeed.fetch_historical` with configured period/interval.

3. **Integrate into runtime startup in `src/cli/runtime.py`**
   - Add private helper:
     - `_resolve_runtime_symbols_with_health_policy(settings: Settings, audit_logger: AuditLogger | None = None) -> list[str]`
   - Call this helper before paper-trial trading loop starts.
   - In strict mode: raise a runtime error if healthy ratio below threshold.
   - In non-strict mode: replace symbol universe with deterministic fallback list.

4. **Add audit visibility**
   - Emit explicit event when substitutions occur:
     - `SYMBOL_UNIVERSE_REMEDIATED`
   - Payload keys:
     - `original_symbols`, `healthy_symbols`, `selected_symbols`, `availability_ratio`, `strict_mode`.

5. **Add tests (new file: `tests/test_symbol_health.py`)**
   - `test_health_eval_all_symbols_healthy`
   - `test_health_eval_partial_health_sorted_deterministically`
   - `test_fallback_selects_at_least_one_when_available`
   - `test_fallback_returns_empty_when_none_healthy`

6. **Add runtime integration tests (extend existing runtime tests)**
   - strict mode + low ratio -> startup block
   - non-strict mode + low ratio -> fallback symbols used
   - audit event emitted on remediation

7. **Update operator docs in `UK_OPERATIONS.md`**
   - Add strict vs auto-remediation explanation.
   - Add example flags/controls.

8. **Validation checks**
   - `python -m pytest tests/test_symbol_health.py -v`
   - `python -m pytest tests/test_ibkr_broker.py tests/test_session_summary.py -v`
   - (optional broader) `python -m pytest tests/ -v`

## Blocking Risks and Mitigations

- **Risk:** Symbol health checks increase startup latency.
  - **Mitigation:** Use short fixed window (`5d`,`1m`) and cache within single startup call.

- **Risk:** Non-deterministic fallback ordering causes test flakiness.
  - **Mitigation:** Sort by `(available desc, bars desc, symbol asc)`.

- **Risk:** Remediation may hide market/data outages.
  - **Mitigation:** Keep strict mode default true and require explicit non-strict opt-in.

## Deliverable Paths

- `docs/NON_TEST_PROGRESS_PROMPT.md`
- `docs/NON_TEST_PROGRESS_RUN_2026-02-25.md`

## Next coding command (non-operational)

`python -m pytest tests/test_ibkr_broker.py tests/test_session_summary.py -v`
