# Risk Architecture Blind Spot Review

> **Version:** 1.0.0
> **Date:** 2026-02-23
> **Scope:** Pre-extended-paper-testing risk review
> **Reviewed By:** Architecture analysis (Claude Opus)
> **Status:** Partially closed — P0 remediations implemented; event-type alignment follow-up open
> **Framework Reference:** `docs/PROMOTION_FRAMEWORK.md`

---

## Executive Summary

This review examines the current risk architecture for blind spots before extended paper testing. Eight risk categories were analysed. The review identified **3 P0 (blocking) gaps**, **3 P1 (urgent) gaps**, and **2 P2 (informational) findings**.

**Immediate actions required before extended paper testing:**
1. Stale data circuit-breaker (P0 — missing entirely)
2. Execution drift alerting (P0 — threshold defined but not monitored over time)
3. Session boundary gap handling (P0 — overnight gaps not explicitly guarded)

---

## Review Methodology

Each risk category is assessed against:
- **Current implementation:** What exists in the codebase today
- **Gap:** What is missing or insufficient
- **Severity:** P0 (blocking), P1 (urgent), P2 (informational)
- **Implementation sketch:** How to remediate
- **Effort:** Estimated hours
- **Test approach:** How to verify the remediation works

---

## 1. Model Drift

**Risk:** Strategy parameters were set at registration time. If market microstructure changes (e.g., average volatility doubles, spread regimes shift), parameters become suboptimal without detection.

### Current Implementation

- Strategy parameters stored in `StrategyRegistry` SQLite table as a JSON blob
- Parameters are fixed at registration; no comparison to current market conditions
- Walk-forward backtest (`backtest/walk_forward.py`) can detect parameter instability, but must be run manually

### Gap

- No automated detection of parameter staleness relative to current market conditions
- No alert when live signal strength distribution drifts significantly from backtest distribution
- No retraining trigger for neural network strategies (when added)
- Walk-forward results are not persisted or compared across time periods

### Severity

**P2 — Informational** (acceptable for paper trading; critical before live)

Rationale: Paper trading with fixed parameters still produces valid paper results. Model drift is most dangerous with real capital. However, monitoring signal distribution should begin now.

### Implementation Sketch

```python
# src/monitoring/drift_detector.py
class SignalDriftDetector:
    """Compare rolling signal distribution vs baseline distribution."""

    def __init__(self, baseline_win_rate: float, baseline_avg_strength: float,
                 window_trades: int = 50, alert_threshold: float = 0.15):
        self.baseline_win_rate = baseline_win_rate
        self.baseline_avg_strength = baseline_avg_strength
        self.window_trades = window_trades
        self.alert_threshold = alert_threshold
        self._recent_strengths: list[float] = []

    def record_signal(self, strength: float) -> None:
        self._recent_strengths.append(strength)
        if len(self._recent_strengths) > self.window_trades:
            self._recent_strengths.pop(0)

    def is_drifted(self) -> tuple[bool, str]:
        if len(self._recent_strengths) < self.window_trades:
            return False, "insufficient data"
        rolling_avg = sum(self._recent_strengths) / len(self._recent_strengths)
        delta = abs(rolling_avg - self.baseline_avg_strength)
        if delta > self.alert_threshold:
            return True, f"signal strength drift: baseline={self.baseline_avg_strength:.3f} rolling={rolling_avg:.3f} delta={delta:.3f}"
        return False, "ok"
```

**Integration:** Call `record_signal()` after each `generate_signal()` and log a `model_drift_warning` audit event when `is_drifted()` returns True.

### Test Approach

- Unit test: inject 50 signals with strengths shifted +0.2 from baseline; assert `is_drifted()` returns True
- Integration test: run backtest, compare signal strength distribution in first vs last quarter of period

### Effort

**3–5 hours** (new file + integration + tests)

---

## 2. Execution Drift

**Risk:** Fill rates decline over time (liquidity conditions change, broker API degrades) and average slippage increases. Currently only point-in-time metrics are computed; no trend detection.

### Current Implementation

- `src/audit/session_summary.py` computes `fill_rate`, `avg_slippage_pct` per session
- `src/audit/reconciliation.py` compares these to fixed expected KPIs from a preset file
- **No time-series tracking** of these metrics — only snapshots per session

### Gap

- Reconciliation compares against a static baseline, not against recent sessions
- Fill rate could decline over 5 sessions from 96% → 89% without triggering any alert (still above the 90% threshold)
- No rolling trend detection (e.g., "slippage has increased 3 sessions in a row")
- No alert for sudden broker API degradation (latency spike)

### Severity

**P0 — Blocking**

Rationale: Execution drift is a leading indicator of strategy deterioration and potential broker issues. Detecting it early prevents extended periods of suboptimal execution going unnoticed. Required before extended paper testing.

### Implementation Sketch

```python
# src/monitoring/execution_trend.py
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class ExecutionSnapshot:
    session_date: str
    fill_rate: float
    avg_slippage_pct: float
    reject_rate: float

class ExecutionTrendMonitor:
    """Detect execution quality degradation over consecutive sessions."""

    def __init__(self, window: int = 5, fill_rate_decline_threshold: float = 0.05,
                 slippage_rise_threshold: float = 0.001):
        self.window = window
        self.fill_rate_decline_threshold = fill_rate_decline_threshold
        self.slippage_rise_threshold = slippage_rise_threshold
        self._snapshots: list[ExecutionSnapshot] = []

    def record_session(self, snapshot: ExecutionSnapshot) -> list[str]:
        """Record a session snapshot and return list of drift warnings (empty = ok)."""
        self._snapshots.append(snapshot)
        if len(self._snapshots) > self.window:
            self._snapshots.pop(0)
        return self._check_trends()

    def _check_trends(self) -> list[str]:
        warnings = []
        if len(self._snapshots) < 3:
            return warnings
        fill_rates = [s.fill_rate for s in self._snapshots]
        slippages = [s.avg_slippage_pct for s in self._snapshots]
        # Monotonic decline in fill rate
        if all(fill_rates[i] >= fill_rates[i+1] for i in range(len(fill_rates)-1)):
            total_decline = fill_rates[0] - fill_rates[-1]
            if total_decline >= self.fill_rate_decline_threshold:
                warnings.append(f"fill_rate declining {len(fill_rates)} consecutive sessions: {fill_rates[0]:.3f} → {fill_rates[-1]:.3f}")
        # Monotonic increase in slippage
        if all(slippages[i] <= slippages[i+1] for i in range(len(slippages)-1)):
            total_rise = slippages[-1] - slippages[0]
            if total_rise >= self.slippage_rise_threshold:
                warnings.append(f"avg_slippage rising {len(slippages)} consecutive sessions: {slippages[0]:.4f} → {slippages[-1]:.4f}")
        return warnings
```

**Integration:** Call after each `paper_session_summary` export. Log `execution_drift_warning` audit events for each warning.

### Test Approach

- Unit test: feed 5 sessions with monotonically declining fill rate; assert warning fires
- Unit test: feed 5 sessions with alternating fill rates; assert no false positive
- Integration test: run two consecutive paper trials; verify comparison runs without error

### Effort

**4–6 hours** (new file + integration into `cmd_paper_trial()` + tests)

---

## 3. Concentration Risk

**Risk:** If multiple symbols are correlated (same sector, same macro factor), position sizing treats them independently but portfolio is effectively concentrated in one risk factor.

### Current Implementation

- `RiskManager._build_buy_order()` checks `max_position_pct` (10%) per symbol
- `max_open_positions` (10) limits total count
- **No correlation-based concentration check** — ten FTSE Energy stocks would each be "within limits" while 100% correlated

### Gap

- No sector-level exposure limit
- No pairwise correlation check before approving a new position
- Portfolio can become de facto concentrated if multiple symbols are driven by the same factor (oil price, BoE rate, etc.)
- `config/test_baskets.json` sector baskets have a `concentration_warning` flag but it is not enforced in code

### Severity

**P1 — Urgent**

Rationale: High during sector basket testing (Phase 3 of UK Test Plan). Must be addressed before testing sector baskets on live capital. Paper testing can proceed with manual monitoring.

### Implementation Sketch

```python
# In src/risk/manager.py — add to RiskManager class

def _check_concentration(self, new_symbol: str, portfolio: PortfolioTracker,
                          baskets: dict, max_sector_pct: float = 0.40) -> Optional[str]:
    """Return rejection reason if sector concentration would be exceeded."""
    # Load sector mapping from config/test_baskets.json (or settings)
    symbol_sector = self._get_symbol_sector(new_symbol, baskets)
    if symbol_sector is None:
        return None  # Unknown sector — skip check

    total_value = portfolio.portfolio_value()
    sector_value = sum(
        pos.market_value
        for sym, pos in portfolio.positions.items()
        if self._get_symbol_sector(sym, baskets) == symbol_sector
    )
    if total_value > 0 and (sector_value / total_value) >= max_sector_pct:
        return (f"Sector concentration limit: {symbol_sector} already at "
                f"{sector_value/total_value:.1%} (max {max_sector_pct:.1%})")
    return None
```

**Config addition:** Add `max_sector_concentration_pct: 0.40` to `RiskConfig` in `config/settings.py`.

### Test Approach

- Unit test: mock portfolio with 35% in energy sector; approve one more energy signal; assert rejection
- Unit test: mock portfolio with 30% in energy sector; assert approval
- Integration test: run backtest with energy-only basket and verify concentration limits fire

### Effort

**5–7 hours** (RiskManager extension + config + tests)

---

## 4. Stale Data

**Risk:** If the market data feed returns stale bars (same timestamp repeated, or bars from >1 trading day ago), strategies will generate signals on stale prices. This can cause incorrect entries and exits.

### Current Implementation

- `MarketDataFeed` (`src/data/feeds.py`) fetches via yfinance
- `BacktestEngine` processes bars in chronological order (zero lookahead by design)
- **No explicit staleness check:** if yfinance returns stale data (cached, rate-limited, or weekend bar), it is consumed silently
- No check on the age of the last bar relative to current wall-clock time

### Gap

- No maximum bar age check before signal generation
- No detection of repeated timestamps in the data stream
- No circuit-breaker that halts trading when data is stale
- Real-time paper trading (`cmd_paper()`) could trade on yesterday's close if the data feed returns a cached bar

### Severity

**P0 — Blocking**

Rationale: Stale data directly causes incorrect signals and orders. This is a correctness issue, not just a risk issue. Must be fixed before any extended paper testing.

### Implementation Sketch

```python
# src/data/feeds.py — add staleness validation

from datetime import datetime, timezone, timedelta

MAX_BAR_AGE_MINUTES = 30  # Configurable; for real-time paper trading

def validate_bar_freshness(bar: Bar, max_age_minutes: int = MAX_BAR_AGE_MINUTES) -> None:
    """Raise ValueError if the bar timestamp is too old for live trading."""
    now = datetime.now(timezone.utc)
    bar_age = now - bar.timestamp
    if bar_age > timedelta(minutes=max_age_minutes):
        raise ValueError(
            f"Stale bar detected: {bar.symbol} timestamp={bar.timestamp.isoformat()} "
            f"age={bar_age.total_seconds()/60:.1f} min > max={max_age_minutes} min"
        )

def validate_no_duplicate_timestamps(bars: list[Bar]) -> None:
    """Raise ValueError if any two bars have the same timestamp."""
    seen = set()
    for bar in bars:
        key = (bar.symbol, bar.timestamp)
        if key in seen:
            raise ValueError(f"Duplicate timestamp for {bar.symbol}: {bar.timestamp.isoformat()}")
        seen.add(key)
```

**Circuit-breaker integration:** In `cmd_paper()`, if `validate_bar_freshness()` raises, log `data_staleness_halt` audit event and halt the session (optionally trigger kill switch).

**Backtest note:** Staleness checks should be **disabled** in `BacktestEngine` (historical data is intentionally "old"). Add a `live_mode: bool` flag to `MarketDataFeed`.

### Test Approach

- Unit test: create a bar with timestamp 2 hours ago; assert `validate_bar_freshness()` raises
- Unit test: create a fresh bar; assert no exception
- Unit test: create two bars with same symbol+timestamp; assert `validate_no_duplicate_timestamps()` raises
- Integration test: mock yfinance to return a stale bar in paper mode; assert session halts cleanly

### Effort

**4–6 hours** (validation functions + circuit-breaker integration + tests)

---

## 5. Session Boundary Risk

**Risk:** Overnight gaps (close price to next open price) can be large. If a strategy holds a position through market close and the next open gaps significantly against the position, the stop-loss price may be "blown through" with no fill at the stop price.

### Current Implementation

- `BacktestEngine` fills orders at next-bar **open** price with slippage — this correctly models gap risk in backtesting
- `PaperBroker.fill_order_at_price()` fills at the provided price — correct for backtest simulation
- `AlpacaBroker` / `IBKRBroker` submit stop-loss orders to the broker — gap risk is real but the broker handles it (limit/stop orders)
- **No explicit overnight gap monitoring** — strategy can hold positions through close with no awareness of expected gap risk

### Gap

- No pre-close position review: strategy may hold a volatile position through an expected news event overnight
- No post-open gap detection: when a large gap occurs on open, there is no alert or circuit-breaker
- Session boundary timestamps not explicitly validated: a bar at 16:35 LSE (after close) should not generate a signal
- `is_market_open()` is used for paper trading but may not be called consistently in all code paths

### Severity

**P0 — Blocking**

Rationale: Gap risk is a direct source of losses that exceed stop-loss levels. The backtest handles it correctly, but the paper trading path lacks explicit safeguards. Must be verified before extended paper testing.

### Implementation Sketch

```python
# src/risk/manager.py — add gap risk awareness

def _check_gap_risk(self, bar: Bar, position: Optional[Position],
                    max_overnight_gap_pct: float = 0.05) -> Optional[str]:
    """Warn if an open price gapped significantly against an existing position."""
    if position is None:
        return None
    if position.side == "long":
        gap_pct = (position.entry_price - bar.open_price) / position.entry_price
    else:
        gap_pct = (bar.open_price - position.entry_price) / position.entry_price
    if gap_pct > max_overnight_gap_pct:
        return (f"Gap risk detected for {bar.symbol}: entry={position.entry_price:.4f} "
                f"open={bar.open_price:.4f} gap={gap_pct:.2%}")
    return None
```

**Session window enforcement:** Ensure `generate_signal()` is only called when `is_market_open(symbol, current_time)` returns True. Add an assertion in `BacktestEngine` and `cmd_paper()` that signals are not generated outside market hours.

**Pre-close review:** In the last 15 minutes of the session, log a `pre_close_position_review` audit event listing all open positions and their current P&L.

### Test Approach

- Unit test: simulate a 6% gap-down against a long position; assert warning logged
- Unit test: simulate a 2% gap (within threshold); assert no warning
- Integration test: verify `is_market_open()` call prevents signal generation outside hours
- Integration test: run a backtest through a known gap event; verify the gap is reflected in P&L

### Effort

**4–5 hours** (gap detection + session window enforcement + pre-close review + tests)

---

## 6. FX Risk

**Risk:** The `PortfolioTracker` converts positions to base currency using a static `fx_rates` dict. If this dict is stale (rates loaded once at startup), FX P&L calculations may be materially incorrect for GBP-base portfolios trading USD-denominated assets.

### Current Implementation

- `PortfolioTracker` accepts `fx_rates: dict[str, float]` at construction time
- Rates are set once (e.g., from `config/settings.py`) and never refreshed
- UK operations use GBP as base; some FTSE 100 stocks have USD earnings that can drive GBP/USD P&L exposure

### Gap

- No FX rate staleness check — rates could be days old
- No alert when GBP/USD moves significantly intraday (e.g., >0.5%)
- No rate refresh mechanism during a long paper session (4+ hours)
- FX P&L attribution is not separately tracked in `session_summary`

### Severity

**P1 — Urgent**

Rationale: During volatile periods (e.g., 2022 mini-budget), GBP/USD moved 5% in a single day. FX errors in position sizing are real but bounded. Fix required before live trading; informational for paper testing.

### Implementation Sketch

```python
# src/portfolio/tracker.py — add FX rate refresh

class PortfolioTracker:
    def __init__(self, initial_cash: float, base_currency: str = "USD",
                 fx_rates: Optional[dict] = None, fx_refresh_interval_minutes: int = 60):
        ...
        self._fx_last_refreshed = datetime.now(timezone.utc)
        self._fx_refresh_interval = timedelta(minutes=fx_refresh_interval_minutes)

    def refresh_fx_rates_if_needed(self) -> None:
        """Refresh FX rates if interval has elapsed. Logs audit event on refresh."""
        now = datetime.now(timezone.utc)
        if now - self._fx_last_refreshed > self._fx_refresh_interval:
            # In production: fetch from FX API or broker
            # In paper: re-load from settings or log a warning
            logger.warning("FX rates may be stale; consider refreshing before position sizing")
            self._fx_last_refreshed = now

    def check_fx_staleness(self, max_age_hours: float = 4.0) -> Optional[str]:
        """Return warning if FX rates are too old."""
        age = (datetime.now(timezone.utc) - self._fx_last_refreshed).total_seconds() / 3600
        if age > max_age_hours:
            return f"FX rates are {age:.1f} hours old (max {max_age_hours}h)"
        return None
```

### Test Approach

- Unit test: construct tracker with rates from 5 hours ago; assert `check_fx_staleness()` returns warning
- Unit test: construct with fresh rates; assert no warning
- Integration test: run paper session for simulated 2 hours; verify FX refresh is logged

### Effort

**3–5 hours** (PortfolioTracker extension + audit event + tests)

---

## 7. Broker Outage Resilience

**Risk:** If the broker API connection drops mid-session (network issue, broker maintenance), the bot may lose track of open positions, submitted orders, and pending fills. On reconnect, internal state may be inconsistent with broker state.

### Current Implementation

- `AlpacaBroker` and `IBKRBroker` make synchronous API calls
- No explicit reconnection logic in `AlpacaBroker` or `IBKRBroker`
- `IBKRBroker` has `connect()/disconnect()` methods but no auto-reconnect
- On restart, in-memory `PortfolioTracker` and `PaperBroker` state is **lost** — positions must be re-fetched from broker

### Gap

- No retry/backoff logic for transient API failures
- No reconciliation on restart: bot restarts with zero in-memory positions
- No detection of partial fills (order submitted, connection dropped before fill event)
- Kill switch only triggers on business logic events; a broker disconnect does not activate it

### Severity

**P1 — Urgent**

Rationale: A broker outage during an extended paper session creates phantom positions (internal state says position open, broker does not). This directly impacts P&L tracking and risk limits. Required before extended paper testing.

### Implementation Sketch

```python
# src/execution/broker.py — add reconnection guard

import functools
import time

def with_retry(max_attempts: int = 3, backoff_seconds: float = 2.0):
    """Decorator: retry broker API calls with exponential backoff."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    wait = backoff_seconds * (2 ** attempt)
                    logger.warning(f"Broker API error (attempt {attempt+1}/{max_attempts}): {e}. Retrying in {wait}s")
                    time.sleep(wait)
        return wrapper
    return decorator

# Apply to submit_order, get_positions, get_portfolio_value, get_cash
```

**State recovery on restart:** Add `restore_from_broker()` method to reconcile in-memory state with broker positions on `cmd_paper()` startup. Reuse `BrokerReconciler` (Prompt 3) for this.

**Disconnect detection:** If `get_positions()` raises 3 consecutive times, activate kill switch with reason `broker_disconnect`.

### Test Approach

- Unit test: mock broker to raise on first call but succeed on second; assert retry works
- Unit test: mock broker to raise 3 times; assert kill switch activates
- Integration test: run paper session, mock a mid-session connection drop, verify audit log records `broker_disconnect`

### Effort

**5–8 hours** (retry decorator + kill switch integration + state recovery + tests)

---

## 8. Audit Trail Integrity

**Risk:** If the audit log can be tampered with (overwritten, deleted, or selectively edited), post-hoc investigation of trading decisions becomes unreliable. This is a compliance and operational risk.

### Current Implementation

- `AuditLogger` (`src/audit/logger.py`) writes to SQLite via an async background queue
- Events are appended (INSERT only — no UPDATE or DELETE in the logger)
- SQLite database is a single file — no write-ahead log checksums
- No cryptographic signing of audit events
- No file-level hash verification of the audit database

### Gap

- SQLite file can be edited with any SQLite editor — no tamper detection
- No periodic checkpoint that proves the log has not been modified retroactively
- No hash chain (each entry contains a hash of the previous entry)
- Audit log and trading database share the same SQLite file path (risk of accidental truncation)

### Severity

**P2 — Informational** (acceptable for paper trading; critical for regulatory compliance on live)

Rationale: Tamper detection is a production/compliance concern. For paper testing, the INSERT-only pattern is sufficient. A hash chain should be implemented before live trading.

### Implementation Sketch

**Option A (simple): Periodic SHA256 checkpoint**
```python
# src/audit/integrity.py
import hashlib, sqlite3

def checkpoint_audit_log(db_path: str, checkpoint_path: str) -> str:
    """Compute SHA256 of entire audit_log table; write to checkpoint file. Returns hash."""
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM audit_log ORDER BY rowid").fetchall()
    content = str(rows).encode()
    sha256 = hashlib.sha256(content).hexdigest()
    Path(checkpoint_path).write_text(sha256)
    return sha256
```

**Option B (robust): Hash chain per event**
```python
# Each INSERT includes: event_hash = SHA256(prev_hash + event_data)
# On startup, verify chain from genesis hash
```

**Recommended:** Option A for immediate implementation (low effort, reasonable assurance). Option B before live trading.

### Test Approach

- Unit test: compute checkpoint hash; modify a row; recompute; assert hashes differ
- Integration test: run paper session; call `checkpoint_audit_log()`; verify checkpoint file exists and is non-empty

### Effort

**Option A: 2–3 hours** | **Option B: 6–8 hours**

---

## Prioritised Remediation Summary

| # | Gap | Severity | Category | Effort (hrs) | Before Paper? | Before Live? |
|---|-----|----------|----------|-------------|--------------|--------------|
| 1 | Stale data circuit-breaker | **P0** | Data Integrity | 4–6 | **Yes** | Yes |
| 2 | Execution drift alerting | **P0** | Execution Quality | 4–6 | **Yes** | Yes |
| 3 | Session boundary gap risk | **P0** | Risk Controls | 4–5 | **Yes** | Yes |
| 4 | Broker outage resilience | P1 | Stability | 5–8 | Yes | Yes |
| 5 | Concentration risk (sector) | P1 | Risk Controls | 5–7 | Yes | Yes |
| 6 | FX rate staleness | P1 | FX Risk | 3–5 | No | **Yes** |
| 7 | Model drift detection | P2 | Model Quality | 3–5 | No | Yes |
| 8 | Audit trail tamper detection | P2 | Compliance | 2–8 | No | **Yes** |

**Total effort before paper:** ~17–25 hours (P0 items only)
**Total effort before live:** ~30–50 hours (all items)

---

## Top 5 Remediations — Implementation Order

### Sprint 1 (This Week — Before Extended Paper)

1. **Stale data circuit-breaker** (4–6 hrs)
   - File: `src/data/feeds.py`
   - Integration: `cmd_paper()` loop
   - Tests: `tests/test_data_freshness.py`

2. **Session boundary enforcement** (4–5 hrs)
   - File: `src/execution/market_hours.py` + `backtest/engine.py`
   - Integration: verify `is_market_open()` called before every signal
   - Tests: extend `tests/test_market_hours.py`

3. **Execution drift monitor** (4–6 hrs)
   - File: `src/monitoring/execution_trend.py` (new)
   - Integration: `cmd_paper_trial()` post-session
   - Tests: `tests/test_execution_trend.py`

### Sprint 2 (Next Week)

4. **Broker outage resilience** (5–8 hrs)
   - File: `src/execution/broker.py` (retry decorator + kill switch integration)
   - Tests: extend `tests/test_ibkr_broker.py`

5. **Concentration risk check** (5–7 hrs)
   - File: `src/risk/manager.py` + `config/settings.py`
   - Tests: extend `tests/test_risk.py`

---

## Acceptance Criteria for Review Sign-Off

This review is considered actioned when:

- [x] All 3 P0 remediations are implemented, tested, and merged
- [x] All tests pass (`python -m pytest tests/ -v`)
- [x] An updated `RISK_ARCHITECTURE_REVIEW.md` is filed with remediation completion dates
- [x] Each remediation references its audit event type so operational monitoring can query them:
    - `DATA_QUALITY_BLOCK` + `KILL_SWITCH_TRIGGERED` (`reason=stale_data_max_consecutive`) — stale data circuit-breaker
    - `EXECUTION_DRIFT_WARNING` — execution drift monitor
    - `DATA_QUALITY_BLOCK` (`reasons` includes `session_gap_seconds:*` / `session_gap_skip_bar`) — session boundary gap handling
    - `BROKER_TRANSIENT_ERROR`, `BROKER_TERMINAL_ERROR`, `BROKER_CIRCUIT_BREAKER_HALT`, `BROKER_RECOVERED` — broker outage resilience
    - `SECTOR_CONCENTRATION_REJECTED` — concentration risk

### Remediation Completion Record (2026-02-23)

- **Stale data circuit-breaker (P0)**
    - Implementation: `src/risk/data_quality.py` (`DataQualityGuard` with stale age + consecutive stale checks)
    - Validation: `tests/test_data_quality_guard.py`
- **Execution drift alerting (P0)**
    - Implementation: `src/monitoring/execution_trend.py` (`ExecutionTrendMonitor` + trend updater)
    - Validation: `tests/test_execution_trend.py`
- **Session boundary gap handling (P0)**
    - Implementation: `src/risk/data_quality.py` (`session_gap_seconds`, `session_gap_skip_bar`) + `src/risk/paper_guardrails.py` session-window gate
    - Validation: `tests/test_data_quality_guard.py`, `tests/test_paper_guardrails.py`
- **Current regression baseline**
    - `python -m pytest tests/ -q` → `352 passed`

---

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 1.0.0 | 2026-02-23 | Initial review — 8 categories, 3 P0, 3 P1, 2 P2. Top 5 remediations defined with effort estimates. |
| 1.1.0 | 2026-02-23 | Recorded P0 remediation completion evidence and test baseline (`341 passed`); left event-type alignment checklist item open. |
| 1.2.0 | 2026-02-23 | Completed event-type alignment with implemented runtime audit events and added sector concentration rejection audit event. |
| 1.3.0 | 2026-02-23 | Refreshed current regression baseline reference to `344 passed` after additional A3 command/tests were added. |
| 1.4.0 | 2026-02-23 | Updated regression baseline reference to `347 passed` after feature/label utilities were added. |
| 1.5.0 | 2026-02-23 | Updated regression baseline reference to `349 passed` after split utilities were added. |
| 1.6.0 | 2026-02-23 | Updated regression baseline reference to `352 passed` after cross-sectional features and manifest logging were added. |
