# MO-2 Live Progress Prompt (While Test Is Running)

Use this prompt when an MO-2 run is currently active or has just failed and you want a fast operational decision.

---

## Prompt

You are working in the trading-bot repo. An MO-2 test is running (or just finished). Progress MO-2 with strict operational discipline.

Constraints:
- Keep `Profile=uk_paper`.
- Keep symbol-data preflight enabled unless I explicitly override.
- Do not change architecture or strategy logic.
- Focus on operational evidence and next-step command only.

Tasks:
1. If a run is active, wait for completion and read the latest MO-2 artifacts.
2. Read these files:
   - latest orchestrator report: `reports/uk_tax/mo2_orchestrator/session_*/mo2_orchestrator_report.json`
   - latest burn-in report: `reports/uk_tax/step1a_burnin/step1a_burnin_latest.json`
   - if present, per-run preflight report: `00_symbol_data_preflight.json`
3. Return a GO/NO-GO with exact reason bucket:
   - `symbol_data_preflight_failed`
   - `criteria_not_met`
   - `command_failed`
   - `outside_allowed_window`
4. Provide one exact next command only:
   - If symbol availability failed, suggest threshold-only adjustment.
   - If criteria failed after running, keep thresholds and suggest rerun timing/action.
5. Append a concise `SESSION_LOG.md` entry with evidence paths and decision.

Output format:
- Decision: GO or NO-GO
- Reason bucket
- Evidence paths
- Next command
- Risk note (1–2 lines)

---

## Threshold-only fallback command (operator-safe)

`./scripts/run_mo2_end_to_end.ps1 -Runs 3 -PaperDurationSeconds 1800 -MinFilledOrders 5 -MinSymbolDataAvailabilityRatio 0.20 -PreflightMinBarsPerSymbol 100`
