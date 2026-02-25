"""Trading Bot runtime command handlers and helpers."""

import asyncio
import glob
import hashlib
import json
import logging
import os
import random
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from config.settings import Settings
from src.audit.logger import AuditLogger
from src.audit.daily_report import DailyReportGenerator
from src.audit.reconciliation import export_paper_reconciliation
from src.audit.session_summary import export_paper_session_summary
from src.audit.uk_tax_export import export_uk_tax_reports
from src.data.feeds import MarketDataFeed
from src.data.symbol_health import apply_symbol_universe_policy
from src.execution.ibkr_broker import IBKRBroker
from src.monitoring.execution_trend import update_execution_trend
from src.promotions.checklist import export_promotion_checklist
from src.reporting.data_quality_report import export_data_quality_report
from src.reporting.execution_dashboard import export_execution_dashboard
from src.strategies.registry import StrategyRegistry
from src.trial.manifest import TrialManifest
from src.trial.runner import TrialAndRunner
from research.bridge.strategy_bridge import load_candidate_bundle, register_candidate_strategy
from src.risk.kill_switch import KillSwitch
from src.risk.manager import RiskManager
from src.strategies.adx_filter import ADXFilterStrategy
from src.strategies.atr_stops import ATRStopsStrategy
from src.strategies.base import BaseStrategy
from src.strategies.bollinger_bands import BollingerBandsStrategy
from src.strategies.ma_crossover import MACrossoverStrategy
from src.strategies.macd_crossover import MACDCrossoverStrategy
from src.strategies.obv_momentum import OBVMomentumStrategy
from src.strategies.pairs_mean_reversion import PairsMeanReversionStrategy
from src.strategies.rsi_momentum import RSIMomentumStrategy
from src.strategies.stochastic_oscillator import StochasticOscillatorStrategy
from backtest.engine import BacktestEngine
from backtest.walk_forward import WalkForwardEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

STRATEGIES = {
    "atr_stops": ATRStopsStrategy,
    "bollinger_bands": BollingerBandsStrategy,
    "ma_crossover": MACrossoverStrategy,
    "macd_crossover": MACDCrossoverStrategy,
    "obv_momentum": OBVMomentumStrategy,
    "pairs_mean_reversion": PairsMeanReversionStrategy,
    "rsi_momentum": RSIMomentumStrategy,
    "stochastic_oscillator": StochasticOscillatorStrategy,
}


def _build_strategy(settings: Settings) -> BaseStrategy:
    strategy_cls = STRATEGIES[settings.strategy.name]
    strategy = strategy_cls(settings)
    if settings.strategy.use_adx_filter:
        strategy = ADXFilterStrategy(settings, strategy)
    return strategy


def _resolve_strategy_class(settings: Settings):
    base_cls = STRATEGIES[settings.strategy.name]
    if not settings.strategy.use_adx_filter:
        return base_cls

    class _ADXWrappedStrategy(ADXFilterStrategy):
        def __init__(self, wrapped_settings: Settings):
            super().__init__(wrapped_settings, base_cls(wrapped_settings))

    _ADXWrappedStrategy.__name__ = f"{base_cls.__name__}ADXWrapped"
    return _ADXWrappedStrategy


def _sqlite_path_from_db_url(db_url: str) -> str:
    parsed = urlparse(db_url)
    if parsed.scheme != "sqlite":
        raise ValueError(f"Only sqlite URLs are supported for local runtime DBs: {db_url}")
    if not parsed.path:
        raise ValueError(f"Invalid sqlite URL path: {db_url}")
    return parsed.path.lstrip("/")


def resolve_runtime_db_path(
    settings: Settings,
    runtime_mode: str,
    explicit_db_path: str | None = None,
) -> str:
    if explicit_db_path:
        return explicit_db_path

    mode = runtime_mode.lower()
    if mode == "paper":
        db_url = settings.db_url_paper
    elif mode == "live":
        db_url = settings.db_url_live
    elif mode == "test":
        db_url = settings.db_url_test
    else:
        db_url = settings.db_url

    if settings.strict_db_isolation and mode in {"paper", "live", "test"}:
        paper_path = _sqlite_path_from_db_url(settings.db_url_paper)
        live_path = _sqlite_path_from_db_url(settings.db_url_live)
        test_path = _sqlite_path_from_db_url(settings.db_url_test)
        if len({paper_path, live_path, test_path}) < 3:
            raise RuntimeError(
                "STRICT_DB_ISOLATION is enabled but DATABASE_URL_PAPER/LIVE/TEST are not distinct."
            )

    return _sqlite_path_from_db_url(db_url)


def _ensure_db_matches_mode(
    settings: Settings,
    runtime_mode: str,
    db_path: str,
    *,
    context: str,
) -> None:
    mode = runtime_mode.lower()
    paper_db = resolve_runtime_db_path(settings, "paper")
    live_db = resolve_runtime_db_path(settings, "live")
    test_db = resolve_runtime_db_path(settings, "test")
    expected = {
        "paper": paper_db,
        "live": live_db,
        "test": test_db,
    }.get(mode)
    if expected is None:
        return
    if db_path != expected:
        raise RuntimeError(
            f"{context} DB mismatch: mode={mode} expects {expected}, got {db_path}"
        )
    if mode == "paper" and db_path in {live_db, test_db}:
        raise RuntimeError(
            f"{context} DB mismatch: paper mode cannot use live/test DB ({db_path})"
        )
    if mode == "live" and db_path in {paper_db, test_db}:
        raise RuntimeError(
            f"{context} DB mismatch: live mode cannot use paper/test DB ({db_path})"
        )
    if mode == "test" and db_path in {paper_db, live_db}:
        raise RuntimeError(
            f"{context} DB mismatch: test mode cannot use paper/live DB ({db_path})"
        )


def _ensure_trading_mode_matches(settings: Settings, runtime_mode: str, *, context: str) -> None:
    expected_paper = runtime_mode.lower() == "paper"
    if settings.broker.paper_trading != expected_paper:
        raise RuntimeError(
            f"{context} trading mode mismatch: runtime={runtime_mode} "
            f"paper_trading={settings.broker.paper_trading}"
        )


def _require_explicit_confirmation(
    mode: str,
    *,
    confirm_paper: bool = False,
    confirm_live: bool = False,
    confirm_paper_trial: bool = False,
) -> None:
    normalized = mode.lower()
    if normalized == "paper" and not confirm_paper:
        print("ERROR: --confirm-paper is required for paper trading.")
        raise SystemExit(2)
    if normalized == "live" and not confirm_live:
        print("ERROR: --confirm-live is required for live trading.")
        raise SystemExit(2)
    if normalized == "paper_trial" and not confirm_paper_trial:
        print("ERROR: --confirm-paper-trial is required for paper_trial mode.")
        raise SystemExit(2)


def apply_runtime_profile(settings: Settings, profile: str) -> None:
    if profile == "uk_paper":
        settings.broker.provider = "ibkr"
        settings.broker.paper_trading = True
        settings.broker.ibkr_port = 7497
        settings.base_currency = "GBP"
        settings.fx_rates = {"USD_GBP": 0.79}
        settings.market_timezone = "Europe/London"
        settings.paper_guardrails.session_timezone = "Europe/London"
        settings.data_quality.enable_stale_check = False  # Disable for yfinance latency tolerance
        # Use short-period MA for 1-min bars (1-min paper streaming uses 2175 bars ~ 1.5 days)
        settings.strategy.fast_period = 5
        settings.strategy.slow_period = 15
        settings.data.symbols = ["HSBA.L", "VOD.L", "BP.L", "BARC.L", "SHEL.L"]
        settings.broker.ibkr_symbol_overrides = {
            "HSBA.L": {
                "ib_symbol": "HSBA",
                "exchange": "SMART",
                "currency": "GBP",
                "primary_exchange": "LSE",
            },
            "VOD.L": {
                "ib_symbol": "VOD",
                "exchange": "SMART",
                "currency": "GBP",
                "primary_exchange": "LSE",
            },
            "BP.L": {
                "ib_symbol": "BP",
                "exchange": "SMART",
                "currency": "GBP",
                "primary_exchange": "LSE",
            },
            "BARC.L": {
                "ib_symbol": "BARC",
                "exchange": "SMART",
                "currency": "GBP",
                "primary_exchange": "LSE",
            },
            "SHEL.L": {
                "ib_symbol": "SHEL",
                "exchange": "SMART",
                "currency": "GBP",
                "primary_exchange": "LSE",
            },
        }


def cmd_backtest(settings: Settings, start: str, end: str) -> None:
    strategy = _build_strategy(settings)
    engine = BacktestEngine(settings, strategy)
    results = engine.run(start, end)
    results.print_report()


def cmd_walk_forward(
    settings: Settings,
    start: str,
    end: str,
    train_months: int,
    test_months: int,
    step_months: int,
) -> None:
    strategy_cls = _resolve_strategy_class(settings)
    wf_engine = WalkForwardEngine(
        settings,
        strategy_cls,
        train_months=train_months,
        test_months=test_months,
        step_months=step_months,
    )
    wf_results = wf_engine.run(start, end)
    wf_results.print_report()


def cmd_uk_tax_export(
    settings: Settings,
    db_path: str,
    output_dir: str,
    *,
    enforce_mode: bool = True,
) -> None:
    if enforce_mode:
        _ensure_db_matches_mode(settings, "paper", db_path, context="uk_tax_export")
    paths = export_uk_tax_reports(
        db_path,
        output_dir,
        base_currency=settings.base_currency,
        fx_rates=settings.fx_rates,
        fx_rate_timestamps=settings.fx_rate_timestamps,
        fx_rate_max_age_hours=settings.fx_rate_max_age_hours,
    )
    logger.info("UK tax export completed")
    logger.info("  trade ledger: %s", paths["trade_ledger"])
    logger.info("  realized gains: %s", paths["realized_gains"])
    logger.info("  fx notes: %s", paths["fx_notes"])


def cmd_paper_session_summary(
    settings: Settings,
    db_path: str,
    output_dir: str,
    *,
    enforce_mode: bool = True,
) -> dict:
    if enforce_mode:
        _ensure_db_matches_mode(settings, "paper", db_path, context="paper_session_summary")
    result = export_paper_session_summary(
        db_path,
        output_dir,
        base_currency=settings.base_currency,
        fx_rates=settings.fx_rates,
        fx_rate_timestamps=settings.fx_rate_timestamps,
        fx_rate_max_age_hours=settings.fx_rate_max_age_hours,
    )
    summary = result["summary"]
    logger.info("Paper session summary export completed")
    logger.info("  json: %s", result["json_path"])
    logger.info("  csv: %s", result["csv_path"])
    logger.info(
        "  fills=%s/%s fill_rate=%.2f%% win_rate=%.2f%% pnl_%s=%.2f",
        summary["filled_order_count"],
        summary["order_attempt_count"],
        float(summary["fill_rate"]) * 100,
        float(summary["win_rate"]) * 100,
        settings.base_currency.lower(),
        float(summary["realized_pnl"]),
    )
    return result


def cmd_paper_reconcile(
    settings: Settings,
    db_path: str,
    output_dir: str,
    expected_json_path: str,
    tolerance_json_path: str | None = None,
    *,
    enforce_mode: bool = True,
) -> int:
    if enforce_mode:
        _ensure_db_matches_mode(settings, "paper", db_path, context="paper_reconcile")
    with open(expected_json_path, encoding="utf-8") as f:
        expected_metrics = json.load(f)
    if isinstance(expected_metrics, dict):
        summary_payload = expected_metrics.get("summary")
        if isinstance(summary_payload, dict):
            expected_metrics = summary_payload
        elif isinstance(expected_metrics.get("metrics"), dict):
            expected_metrics = expected_metrics["metrics"]
    tolerances = None
    if tolerance_json_path:
        with open(tolerance_json_path, encoding="utf-8") as f:
            tolerances = json.load(f)

    result = export_paper_reconciliation(
        db_path,
        output_dir,
        expected_metrics,
        base_currency=settings.base_currency,
        fx_rates=settings.fx_rates,
        fx_rate_timestamps=settings.fx_rate_timestamps,
        fx_rate_max_age_hours=settings.fx_rate_max_age_hours,
        tolerances=tolerances,
    )
    report = result["report"]
    logger.info("Paper reconciliation export completed")
    logger.info("  json: %s", result["json_path"])
    logger.info("  csv: %s", result["csv_path"])
    logger.info(
        "  metrics=%s drift_flags=%s status=%s",
        report["metric_count"],
        report["drift_flag_count"],
        "ok" if report["ok"] else "drift_detected",
    )
    return int(report["drift_flag_count"])


def cmd_execution_dashboard(
    settings: Settings,
    db_path: str,
    output_path: str,
    *,
    refresh_seconds: int = 60,
) -> None:
    result = export_execution_dashboard(
        db_path,
        output_path,
        refresh_seconds=refresh_seconds,
    )
    metrics = result["metrics"]
    logger.info("Execution dashboard export completed")
    logger.info("  html: %s", result["output_path"])
    logger.info("  events=%s symbols=%s", metrics["event_count"], len(metrics["reject_rate_by_symbol"]))


def cmd_data_quality_report(
    settings: Settings,
    db_path: str,
    output_path: str,
    *,
    dashboard_path: str = "reports/execution_dashboard.html",
) -> None:
    result = export_data_quality_report(
        db_path,
        output_path,
        dashboard_path=dashboard_path,
    )
    report = result["report"]
    logger.info("Data quality report export completed")
    logger.info("  json: %s", result["output_path"])
    logger.info("  dashboard: %s", result["dashboard_path"])
    logger.info("  symbols_checked=%s", report["symbols_checked"])


def cmd_daily_report(
    settings: Settings,
    db_path: str,
    *,
    output_dir: str,
    report_date: str | None = None,
    notify_email: str | None = None,
) -> dict:
    """Generate and persist a daily P&L summary report."""
    generator = DailyReportGenerator(db_path)
    report = generator.build_report(report_date=report_date)
    report_path = generator.write_report(report, output_dir=output_dir)

    target_email = notify_email or os.getenv("NOTIFY_EMAIL")
    if target_email:
        DailyReportGenerator.send_email(report, target_email)

    logger.info("Daily report generated")
    logger.info("  json: %s", report_path)
    logger.info("  fills=%s pnl_proxy=%.4f", report["fills"], report["pnl_proxy_mark_to_close"])
    print(json.dumps(report, indent=2))
    return {
        "report": report,
        "path": report_path,
    }


def cmd_promotion_checklist(
    settings: Settings,
    *,
    strategy: str,
    output_dir: str,
    summary_json_path: str | None = None,
    audit_db_path: str | None = None,
) -> None:
    result = export_promotion_checklist(
        output_dir,
        strategy,
        summary_json_path=summary_json_path,
        base_currency=settings.base_currency,
    )
    if audit_db_path:
        _log_promotion_checklist_event(
            audit_db_path,
            strategy=strategy,
            decision=result["decision"],
            output_path=result["output_path"],
        )
    logger.info("Promotion checklist export completed")
    logger.info("  json: %s", result["output_path"])
    logger.info("  decision: %s", result["decision"])


def cmd_research_register_candidate(
    settings: Settings,
    *,
    candidate_dir: str,
    output_dir: str | None = None,
    registry_db_path: str = "trading.db",
    artifacts_dir: str = "strategies",
    reviewer_1: str = "copilot",
    reviewer_2: str = "pending_second_reviewer",
) -> dict:
    candidate = load_candidate_bundle(candidate_dir)
    candidate_root = Path(candidate_dir)
    strategy_type = str(candidate["strategy_type"]).strip().lower()

    model_path = candidate_root / "model.pt"
    weights = model_path.read_bytes() if model_path.exists() else None

    if strategy_type == "nn" and weights is None:
        raise ValueError("NN candidate requires model.pt in candidate directory")

    sha_actual = None
    sha_verified = False
    if weights is not None:
        sha_actual = hashlib.sha256(weights).hexdigest()
        sha_verified = sha_actual == str(candidate.get("artifact_sha256", ""))

    registry = StrategyRegistry(db_path=registry_db_path, artifacts_dir=artifacts_dir)
    strategy_id = register_candidate_strategy(registry, candidate, weights=weights)

    experiment_id = str(candidate.get("experiment_id") or "unknown_experiment")
    out_root = Path(output_dir) if output_dir else Path("research") / "experiments" / experiment_id
    out_root.mkdir(parents=True, exist_ok=True)
    gate_path = out_root / "integration_gate.json"

    gate_payload = {
        "experiment_id": experiment_id,
        "stage": "R2",
        "decision": "PASS",
        "strategy_registry_id": strategy_id,
        "registry_status": "experimental",
        "reviewer_1": reviewer_1,
        "reviewer_2": reviewer_2,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "candidate_dir": str(candidate_root),
        "registry_db_path": registry_db_path,
        "artifacts_dir": artifacts_dir,
        "artifact_sha256_expected": candidate.get("artifact_sha256"),
        "artifact_sha256_actual": sha_actual,
        "artifact_sha256_verified": sha_verified if weights is not None else None,
    }
    gate_path.write_text(json.dumps(gate_payload, indent=2), encoding="utf-8")

    logger.info("Research candidate registration completed")
    logger.info("  strategy_id: %s", strategy_id)
    logger.info("  integration_gate: %s", gate_path)
    logger.info("  sha256_verified: %s", gate_payload["artifact_sha256_verified"])

    return {
        "strategy_id": strategy_id,
        "integration_gate_path": str(gate_path),
        "sha256_verified": gate_payload["artifact_sha256_verified"],
    }


def _log_promotion_checklist_event(
    db_path: str,
    *,
    strategy: str,
    decision: str,
    output_path: str,
) -> None:
    async def _write() -> None:
        audit = AuditLogger(db_path)
        await audit.start()
        await audit.log_event(
            "PROMOTION_CHECKLIST",
            {
                "strategy": strategy,
                "decision": decision,
                "output_path": output_path,
            },
            strategy=strategy,
            severity="info",
        )
        await audit.flush()
        await audit.stop()

    asyncio.run(_write())


def _log_execution_drift_events(db_path: str, warnings: list[str]) -> None:
    async def _write() -> None:
        audit = AuditLogger(db_path)
        await audit.start()
        for warning in warnings:
            await audit.log_event(
                "EXECUTION_DRIFT_WARNING",
                {"warning": warning},
                severity="warning",
            )
        await audit.flush()
        await audit.stop()

    asyncio.run(_write())


def _log_symbol_universe_remediation_event(db_path: str, payload: dict[str, Any]) -> None:
    async def _write() -> None:
        audit = AuditLogger(db_path)
        await audit.start()
        await audit.log_event(
            "SYMBOL_UNIVERSE_REMEDIATED",
            payload,
            severity="warning",
        )
        await audit.flush()
        await audit.stop()

    asyncio.run(_write())


async def _run_paper_for_duration(
    settings: Settings,
    duration_seconds: int,
    broker=None,
    auto_rotate_at_start: bool = True,
) -> None:
    try:
        await asyncio.wait_for(
            cmd_paper(settings, broker=broker, auto_rotate_at_start=auto_rotate_at_start),
            timeout=max(duration_seconds, 1),
        )
    except asyncio.TimeoutError:
        logger.info("Paper trial duration reached (%ss); stopping session", duration_seconds)


def cmd_paper_trial(
    settings: Settings,
    *,
    duration_seconds: int,
    db_path: str,
    output_dir: str,
    expected_json_path: str | None = None,
    tolerance_json_path: str | None = None,
    strict_reconcile: bool = False,
    skip_health_check: bool = False,
    skip_rotate: bool = False,
) -> int:
    """Run an end-to-end paper trial: checks -> paper run -> summary -> reconcile."""
    import time
    from src.execution.ibkr_broker import IBKRBroker
    
    settings.broker.paper_trading = True
    _ensure_db_matches_mode(settings, "paper", db_path, context="paper_trial")

    if not skip_health_check:
        health_errors = cmd_uk_health_check(settings, with_data_check=False, json_output=False)
        if health_errors > 0:
            logger.error("Paper trial aborted: health check reported %s blocking error(s)", health_errors)
            return 2
        # Allow event loop to fully clean up after health check broker disconnect
        time.sleep(0.5)

    symbol_policy = apply_symbol_universe_policy(settings)
    policy_summary = symbol_policy["health_summary"]
    if not symbol_policy["allowed"]:
        logger.error(
            "Paper trial blocked by symbol-universe health policy: reason=%s "
            "availability=%.2f threshold=%.2f healthy=%s/%s",
            symbol_policy["reason"],
            policy_summary["availability_ratio"],
            policy_summary["threshold_ratio"],
            policy_summary["healthy_symbols"],
            policy_summary["total_symbols"],
        )
        return 2

    if symbol_policy["remediated"]:
        selected_symbols = list(symbol_policy["selected_symbols"])
        removed_symbols = list(symbol_policy["removed_symbols"])
        settings.data.symbols = selected_symbols
        logger.warning(
            "Symbol-universe remediation applied: selected=%s removed=%s",
            selected_symbols,
            removed_symbols,
        )
        _log_symbol_universe_remediation_event(
            db_path,
            {
                "selected_symbols": selected_symbols,
                "removed_symbols": removed_symbols,
                "availability_ratio": policy_summary["availability_ratio"],
                "threshold_ratio": policy_summary["threshold_ratio"],
                "healthy_symbols": policy_summary["healthy_symbols"],
                "total_symbols": policy_summary["total_symbols"],
                "reason": symbol_policy["reason"],
            },
        )

    if not skip_rotate:
        cmd_rotate_paper_db(
            settings,
            archive_dir=settings.paper_db_archive_dir,
            keep_original=False,
        )

    # Create IBKR broker BEFORE entering async context to avoid event loop conflicts
    broker = None
    if settings.broker.provider.lower() == "ibkr":
        broker = IBKRBroker(settings)
    
    logger.info("Starting timed paper trial for %ss", duration_seconds)
    try:
        asyncio.run(
            _run_paper_for_duration(
                settings,
                duration_seconds,
                broker=broker,
                auto_rotate_at_start=False,
            )
        )
    finally:
        if broker is not None:
            broker.disconnect()

    summary_result = cmd_paper_session_summary(settings, db_path, output_dir)

    if summary_result and "summary" in summary_result:
        trend_path = str(Path(output_dir) / "execution_trend.json")
        trend_result = update_execution_trend(summary_result["summary"], trend_path)
        if trend_result["warnings"]:
            _log_execution_drift_events(db_path, trend_result["warnings"])

    if expected_json_path:
        drift_count = cmd_paper_reconcile(
            settings,
            db_path,
            output_dir,
            expected_json_path,
            tolerance_json_path,
        )
        if strict_reconcile and drift_count > 0:
            return 1

    return 0


def cmd_trial_batch(
    settings: Settings,
    *,
    manifest_patterns: list[str],
    output_dir: str,
    parallel: bool = False,
) -> dict:
    """Run multiple paper trials from manifest files and produce aggregate report."""
    expanded_paths: list[str] = []
    seen: set[str] = set()
    for pattern in manifest_patterns:
        matches = sorted(glob.glob(pattern))
        if not matches and Path(pattern).exists():
            matches = [pattern]
        for match in matches:
            if match not in seen:
                seen.add(match)
                expanded_paths.append(match)

    if not expanded_paths:
        raise ValueError("No trial manifests matched the provided --manifests patterns")

    manifests = [TrialManifest.from_json(path) for path in expanded_paths]

    def _execute_manifest(manifest: TrialManifest) -> dict:
        trial_settings = Settings()
        apply_runtime_profile(trial_settings, manifest.profile)
        trial_settings.strategy.name = manifest.strategy
        trial_settings.initial_capital = manifest.capital
        if manifest.symbols:
            trial_settings.data.symbols = manifest.symbols

        trial_db_path = manifest.db_path or resolve_runtime_db_path(trial_settings, "paper")
        exit_code = cmd_paper_trial(
            trial_settings,
            duration_seconds=manifest.duration_seconds,
            db_path=trial_db_path,
            output_dir=manifest.output_dir,
            expected_json_path=manifest.expected_json,
            tolerance_json_path=manifest.tolerance_json,
            strict_reconcile=manifest.strict_reconcile,
            skip_health_check=manifest.skip_health_check,
            skip_rotate=manifest.skip_rotate,
        )

        summary_path = Path(manifest.output_dir) / "paper_session_summary.json"
        summary: dict = {}
        if summary_path.exists():
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                summary = payload.get("summary", payload)

        return {
            "exit_code": exit_code,
            "summary": summary,
            "output_dir": manifest.output_dir,
        }

    runner = TrialAndRunner(_execute_manifest, parallel=parallel)
    report = runner.run(manifests, output_dir)
    logger.info("Trial batch completed")
    logger.info("  report: %s", report["report_path"])
    logger.info(
        "  trials=%s success=%s failed=%s overall_passed=%s",
        report["trial_count"],
        report["successful_trials"],
        report["failed_trials"],
        report["overall_passed"],
    )
    return report


def cmd_rotate_paper_db(
    settings: Settings,
    *,
    archive_dir: str = "archives/db",
    keep_original: bool = False,
    suffix: str | None = None,
) -> dict:
    """Archive current paper DB file and optionally keep original in place."""
    paper_db_path = resolve_runtime_db_path(settings, "paper")
    src = Path(paper_db_path)
    if not src.exists():
        logger.warning("Paper DB not found, nothing to rotate: %s", src)
        return {
            "rotated": False,
            "source": str(src),
            "archive": None,
            "keep_original": keep_original,
        }

    stamp = suffix or datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_root = Path(archive_dir)
    archive_root.mkdir(parents=True, exist_ok=True)
    target = archive_root / f"{src.stem}_{stamp}{src.suffix}"

    if keep_original:
        shutil.copy2(src, target)
        logger.info("Paper DB copied to archive: %s", target)
    else:
        try:
            shutil.move(str(src), str(target))
            logger.info("Paper DB moved to archive: %s", target)
        except PermissionError:
            shutil.copy2(src, target)
            logger.warning(
                "Paper DB in use; archived via copy (source retained): %s",
                target,
            )
            keep_original = True

    return {
        "rotated": True,
        "source": str(src),
        "archive": str(target),
        "keep_original": keep_original,
    }


def cmd_uk_health_check(
    settings: Settings,
    with_data_check: bool = False,
    json_output: bool = False,
) -> int:
    """Run UK pre-flight checks and return number of blocking errors."""
    errors = 0
    checks: list[dict] = []

    def ok(msg: str, check: str) -> None:
        checks.append({"check": check, "status": "ok", "message": msg})
        logger.info("[OK] %s", msg)

    def warn(msg: str, check: str) -> None:
        checks.append({"check": check, "status": "warning", "message": msg})
        logger.warning("[WARN] %s", msg)

    def fail(msg: str, check: str) -> None:
        nonlocal errors
        errors += 1
        checks.append({"check": check, "status": "fail", "message": msg})
        logger.error("[FAIL] %s", msg)

    if settings.broker.provider.lower() == "ibkr":
        ok("Broker provider is IBKR", "broker_provider")
    else:
        warn("Broker provider is not IBKR (expected for UK workflow)", "broker_provider")

    if settings.market_timezone == "Europe/London":
        ok("Market timezone is Europe/London", "market_timezone")
    else:
        warn(
            f"Market timezone is {settings.market_timezone} (expected Europe/London)",
            "market_timezone",
        )

    if settings.base_currency.upper() == "GBP":
        ok("Base currency is GBP", "base_currency")
    else:
        warn(f"Base currency is {settings.base_currency} (expected GBP)", "base_currency")

    uk_symbols = [s for s in settings.data.symbols if s.upper().endswith(".L")]
    if uk_symbols:
        ok(f"Detected UK symbols: {', '.join(uk_symbols)}", "symbols")
    else:
        warn("No .L symbols detected; UK market profile may be misconfigured", "symbols")

    try:
        paper_db = resolve_runtime_db_path(settings, "paper")
        live_db = resolve_runtime_db_path(settings, "live")
        test_db = resolve_runtime_db_path(settings, "test")
        if len({paper_db, live_db, test_db}) == 3:
            ok(
                f"DB isolation paths set (paper={paper_db}, live={live_db}, test={test_db})",
                "db_isolation",
            )
        else:
            fail("Database paths for paper/live/test are not distinct", "db_isolation")
    except Exception as exc:
        fail(f"Database isolation check failed: {exc}", "db_isolation")

    if settings.broker.provider.lower() == "ibkr":
        broker = IBKRBroker(settings)
        try:
            if broker._connected():
                ok("IBKR connection established", "ibkr_connection")
            else:
                fail("IBKR connection not established (is TWS/Gateway running?)", "ibkr_connection")

            account = broker.get_primary_account()
            if account:
                mode = "paper" if broker.is_paper_account() else "live"
                ok(f"IBKR account detected: {account} ({mode})", "ibkr_account")
                if settings.broker.paper_trading and broker.is_live_account():
                    fail("Running in paper mode but connected account appears live", "ibkr_mode_match")
                if (not settings.broker.paper_trading) and broker.is_paper_account():
                    fail("Running in live mode but connected account appears paper", "ibkr_mode_match")
            else:
                warn("IBKR account not detected yet", "ibkr_account")
        finally:
            if hasattr(broker, "disconnect"):
                broker.disconnect()

    if with_data_check:
        try:
            feed = MarketDataFeed(settings)
            symbol = settings.data.symbols[0]
            df = feed.fetch_historical(symbol, period="5d", interval="1d")
            if df.empty:
                fail(f"Data check returned no bars for {symbol}", "data_check")
            else:
                ok(f"Data check passed for {symbol} ({len(df)} bars)", "data_check")
        except Exception as exc:
            fail(f"Data check failed: {exc}", "data_check")

    if errors == 0:
        logger.info("UK health check complete: no blocking errors")
    else:
        logger.error("UK health check complete: %s blocking error(s)", errors)

    if json_output:
        report = {
            "ok": errors == 0,
            "blocking_errors": errors,
            "profile": "uk_paper",
            "checks": checks,
        }
        print(json.dumps(report, separators=(",", ":")))
    return errors


async def cmd_paper(settings: Settings, broker=None, auto_rotate_at_start: bool = True) -> None:
    from src.execution.ibkr_broker import IBKRBroker
    from src.portfolio.tracker import PortfolioTracker
    from src.risk.data_quality import DataQualityGuard
    from src.trading.loop import TradingLoopHandler, build_runtime_broker
    from src.trading.stream_events import (
        build_stream_error_handler,
        build_stream_heartbeat_handler,
    )

    runtime_mode = "paper" if settings.broker.paper_trading else "live"
    _ensure_trading_mode_matches(settings, runtime_mode, context="paper_live")
    if runtime_mode == "paper" and settings.auto_rotate_paper_db and auto_rotate_at_start:
        result = cmd_rotate_paper_db(
            settings,
            archive_dir=settings.paper_db_archive_dir,
            keep_original=False,
        )
        if result["rotated"]:
            logger.info("Auto-rotated paper DB to: %s", result["archive"])

    strategy = _build_strategy(settings)
    risk = RiskManager(settings)
    
    # Use pre-created broker if provided, otherwise create new one
    if broker is None:
        broker = build_runtime_broker(settings)
    
    if broker is not None:
        if isinstance(broker, IBKRBroker):
            account = broker.get_primary_account()
            if account:
                account_mode = "paper" if broker.is_paper_account() else "live"
                logger.info(f"IBKR account detected: {account} ({account_mode})")
            if settings.broker.paper_trading and broker.is_live_account():
                raise RuntimeError(
                    "IBKR live account detected while running in paper mode. "
                    "Switch to paper account (DUxxxxxx) in TWS/Gateway."
                )
            if (not settings.broker.paper_trading) and broker.is_paper_account():
                raise RuntimeError(
                    "IBKR paper account detected while running in live mode. "
                    "Switch to a funded live account before proceeding."
                )
        elif hasattr(broker, "is_paper_mode"):
            actual_paper = broker.is_paper_mode()
            if settings.broker.paper_trading and not actual_paper:
                raise RuntimeError(
                    "Alpaca live endpoint detected while running in paper mode."
                )
            if (not settings.broker.paper_trading) and actual_paper:
                raise RuntimeError(
                    "Alpaca paper endpoint detected while running in live mode."
                )
    
    tracker = PortfolioTracker(settings.initial_capital)
    feed = MarketDataFeed(settings)
    data_quality = DataQualityGuard(
        max_bar_age_seconds=settings.data_quality.max_bar_age_seconds,
        max_bar_gap_seconds=settings.data_quality.max_bar_gap_seconds,
        max_consecutive_stale=settings.data_quality.max_consecutive_stale,
        session_gap_skip_bars=settings.data_quality.session_gap_skip_bars,
    )
    runtime_db_path = resolve_runtime_db_path(settings, runtime_mode)
    _ensure_db_matches_mode(settings, runtime_mode, runtime_db_path, context="paper_live")
    logger.info("Runtime DB (%s): %s", runtime_mode, runtime_db_path)
    kill_switch = KillSwitch(runtime_db_path)
    audit = AuditLogger(runtime_db_path)
    await audit.start()

    pending_audit_tasks: set[asyncio.Task] = set()
    broker_retry_state: dict[str, int] = {"consecutive_failures": 0}

    def _track_task(task: asyncio.Task) -> None:
        pending_audit_tasks.add(task)

        def _done(t: asyncio.Task) -> None:
            pending_audit_tasks.discard(t)
            try:
                t.result()
            except Exception as exc:
                logger.error("Audit task failed: %s", exc)

        task.add_done_callback(_done)

    def enqueue_audit(
        event_type: str,
        payload: dict,
        *,
        symbol: str | None = None,
        strategy: str | None = None,
        severity: str = "info",
    ) -> None:
        task = asyncio.create_task(
            audit.log_event(
                event_type,
                payload,
                symbol=symbol,
                strategy=strategy,
                severity=severity,
            )
        )
        _track_task(task)

    await audit.log_event(
        "SESSION_START",
        {
            "mode": "paper" if settings.broker.paper_trading else "live",
            "broker": settings.broker.provider,
            "symbols": settings.data.symbols,
            "strategy": settings.strategy.name,
            "base_currency": settings.base_currency,
        },
        strategy=settings.strategy.name,
    )

    handler = TradingLoopHandler(
        settings=settings,
        strategy=strategy,
        risk=risk,
        broker=broker,
        tracker=tracker,
        data_quality=data_quality,
        kill_switch=kill_switch,
        audit=audit,
        enqueue_audit=enqueue_audit,
        broker_retry_state=broker_retry_state,
    )
    handler._prewarm_strategy(feed)

    logger.info(
        f"Paper trading started. "
        f"Min bars required: {strategy.min_bars_required()}. "
        f"Polling every 300s. Ctrl+C to stop."
    )
    handler.initialize_portfolio_value()

    try:
        on_stream_heartbeat = build_stream_heartbeat_handler(
            enqueue_audit,
            settings.strategy.name,
        )
        on_stream_error = build_stream_error_handler(
            enqueue_audit,
            settings.strategy.name,
            kill_switch,
        )

        await feed.stream(
            settings.data.symbols,
            handler.on_bar,
            interval_seconds=300,
            heartbeat_callback=on_stream_heartbeat,
            error_callback=on_stream_error,
            backoff_base_seconds=float(getattr(settings.broker, "outage_backoff_base_seconds", 0.25) or 0.25),
            backoff_max_seconds=float(getattr(settings.broker, "outage_backoff_max_seconds", 2.0) or 2.0),
            max_consecutive_failure_cycles=int(getattr(settings.broker, "outage_consecutive_failure_limit", 3) or 3),
        )
    finally:
        await audit.log_event(
            "SESSION_END",
            {
                "mode": "paper" if settings.broker.paper_trading else "live",
                "broker": settings.broker.provider,
                "strategy": settings.strategy.name,
            },
            strategy=settings.strategy.name,
        )
        if pending_audit_tasks:
            await asyncio.gather(*list(pending_audit_tasks), return_exceptions=True)
        await audit.flush()
        await audit.stop()

        if settings.broker.provider.lower() == "ibkr" and hasattr(broker, "disconnect"):
            try:
                broker.disconnect()
            except Exception as exc:
                logger.error("Broker cleanup failed: %s", exc)


