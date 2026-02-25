# MO-2 Progress Prompt (Copy/Paste)

Use this prompt in a fresh Copilot session to drive MO-2 forward with the current guardrails.

---

## Prompt

You are working in the trading-bot repo. Progress MO-2 operationally using existing scripts and reports.

Constraints:
- Keep `Profile=uk_paper`.
- Keep symbol-data preflight enabled (do NOT use `-SkipSymbolAvailabilityPreflight` unless I explicitly ask).
- Use in-window execution assumptions (08:00–16:00 UTC).
- Do not make architecture changes.

Tasks:
1. Run one guarded MO-2 preflight attempt using:
   `./scripts/run_mo2_end_to_end.ps1 -Runs 3 -PaperDurationSeconds 1800 -MinFilledOrders 5 -MinSymbolDataAvailabilityRatio 0.80 -PreflightMinBarsPerSymbol 100`
2. If the run fails early, inspect:
   - latest orchestrator report in `reports/uk_tax/mo2_orchestrator/session_*/mo2_orchestrator_report.json`
   - latest burn-in report in `reports/uk_tax/step1a_burnin/step1a_burnin_latest.json`
   - per-run preflight file `00_symbol_data_preflight.json`
3. Return a concise GO/NO-GO decision with:
   - failure gate (`symbol_data_preflight_failed`, `criteria_not_met`, or command/runtime failure)
   - symbol availability ratio and which symbols were unavailable
   - exact next command to run
4. If NO-GO due to symbol availability, propose a strict, minimal operator-safe command adjustment (threshold only) and explain trade-off.
5. Append a short `SESSION_LOG.md` entry with evidence paths and decision.

Output format:
- Decision: GO or NO-GO
- Evidence paths (clickable relative paths)
- Next command
- One-paragraph rationale

---

## Optional stricter variant

Use this when you want to require full symbol health:

`./scripts/run_mo2_end_to_end.ps1 -Runs 3 -PaperDurationSeconds 1800 -MinFilledOrders 5 -MinSymbolDataAvailabilityRatio 1.0 -PreflightMinBarsPerSymbol 100`
