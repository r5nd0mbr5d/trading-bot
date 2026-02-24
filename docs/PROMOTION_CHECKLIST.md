# Promotion Checklist (Operational)

Operational checklist for promoting a strategy from paper-ready toward live approval.

## Scope

This checklist complements:
- `docs/PROMOTION_FRAMEWORK.md`
- `reports/promotions/decision_rubric.json`
- `src/strategies/registry.py` (`paper_readiness_failures`)

## Pre-Paper Checks

- All tests pass (`python -m pytest tests/ -v`)
- Backtest + walk-forward reports reviewed
- Strategy registry status is `approved_for_paper`

## In-Paper Checks

- UK health check green (`uk_health_check --strict-health`)
- Reconciliation drift below 5%
- Paper readiness thresholds pass (`paper_readiness_failures()` returns no failures)

## Exit Criteria

- Decision rubric completed and stored under `reports/promotions/`
- Manual reviewer sign-off captured
- Final decision is one of: `READY`, `NOT_READY`

## CLI

Generate checklist JSON:

```bash
python main.py promotion_checklist --strategy ma_crossover --output-dir reports/promotions --summary-json reports/session/paper_session_summary.json
```

Note: `StrategyRegistry.promote(..., new_status="approved_for_live")` now requires a checklist file with `decision=READY`.

Output:
- `reports/promotions/promotion_checklist.json`
