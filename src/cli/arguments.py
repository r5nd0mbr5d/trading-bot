"""CLI argument parser and mode dispatcher for the trading bot entrypoint."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from config.settings import Settings
from src.trial.manifest import TrialManifest

MODE_CHOICES = [
    "backtest",
    "walk_forward",
    "paper",
    "live",
    "uk_tax_export",
    "uk_health_check",
    "rotate_paper_db",
    "paper_session_summary",
    "paper_reconcile",
    "paper_trial",
    "trial_batch",
    "execution_dashboard",
    "data_quality_report",
    "daily_report",
    "promotion_checklist",
    "research_register_candidate",
    "research_train_xgboost",
    "research_download_ticks",
    "research_build_tick_splits",
    "research_ingest_flat_files",
]


def build_argument_parser(strategy_choices: Iterable[str]) -> argparse.ArgumentParser:
    """Build the application CLI parser.

    Args:
        strategy_choices: Available strategy names for --strategy choices.

    Returns:
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(description="Algorithmic Trading Bot")
    parser.add_argument("mode", choices=MODE_CHOICES)
    parser.add_argument("--start", default="2022-01-01")
    parser.add_argument("--end", default=datetime.today().strftime("%Y-%m-%d"))
    parser.add_argument("--strategy", default="ma_crossover", choices=list(strategy_choices))
    parser.add_argument("--symbols", nargs="+", default=None)
    parser.add_argument("--capital", type=float, default=100_000.0)
    parser.add_argument("--broker", choices=["alpaca", "ibkr"], default=None)
    parser.add_argument("--profile", choices=["default", "uk_paper"], default="default")
    parser.add_argument("--no-market-hours", action="store_true")
    parser.add_argument("--with-data-check", action="store_true")
    parser.add_argument("--health-json", action="store_true")
    parser.add_argument("--strict-health", action="store_true")
    parser.add_argument("--db-path", default=None)
    parser.add_argument("--output-dir", default="reports/uk_tax")
    parser.add_argument("--output", default=None)
    parser.add_argument("--refresh-seconds", type=int, default=60)
    parser.add_argument("--summary-json", default=None)
    parser.add_argument("--report-date", default=None)
    parser.add_argument("--notify-email", default=None)
    parser.add_argument("--audit-db-path", default=None)
    parser.add_argument("--candidate-dir", default=None)
    parser.add_argument("--registry-db-path", default="trading.db")
    parser.add_argument("--artifacts-dir", default="strategies")
    parser.add_argument("--reviewer-1", default="copilot")
    parser.add_argument("--reviewer-2", default="pending_second_reviewer")
    parser.add_argument("--config", default=None)
    parser.add_argument("--snapshot-dir", default=None)
    parser.add_argument("--experiment-id", default=None)
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--tick-provider", default="polygon", choices=["polygon"])
    parser.add_argument("--tick-date", default=None)
    parser.add_argument("--tick-start-date", default=None)
    parser.add_argument("--tick-end-date", default=None)
    parser.add_argument("--tick-api-key", default=None)
    parser.add_argument("--tick-output-dir", default="research/data/ticks")
    parser.add_argument("--tick-limit", type=int, default=50000)
    parser.add_argument("--tick-max-pages", type=int, default=20)
    parser.add_argument("--tick-build-manifest", action="store_true")
    parser.add_argument("--tick-manifest-path", default=None)
    parser.add_argument("--tick-input-manifest", default=None)
    parser.add_argument("--tick-split-output-dir", default="research/data/ticks/splits")
    parser.add_argument("--tick-train-end", default=None)
    parser.add_argument("--tick-val-end", default=None)
    parser.add_argument("--flat-output-dir", default="research/data/snapshots")
    parser.add_argument("--flat-manifest-path", default=None)
    parser.add_argument("--flat-skip-existing", action="store_true")
    parser.add_argument("--horizon-days", type=int, default=5)
    parser.add_argument("--train-ratio", type=float, default=0.6)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--gap-days", type=int, default=0)
    parser.add_argument("--walk-forward", action="store_true")
    parser.add_argument("--train-months", type=int, default=6)
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--test-months", type=int, default=3)
    parser.add_argument("--step-months", type=int, default=3)
    parser.add_argument("--feature-version", default="v1")
    parser.add_argument("--label-version", default="h5")
    parser.add_argument("--xgb-params-json", default=None)
    parser.add_argument("--xgb-preset", default=None)
    parser.add_argument("--xgb-presets-path", default="research/experiments/configs/xgb_params_presets.json")
    parser.add_argument("--print-presets", action="store_true")
    parser.add_argument("--calibrate", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--expected-json", default=None)
    parser.add_argument("--tolerance-json", default=None)
    parser.add_argument("--strict-reconcile", action="store_true")
    parser.add_argument("--paper-duration-seconds", type=int, default=900)
    parser.add_argument("--skip-health-check", action="store_true")
    parser.add_argument("--skip-rotate", action="store_true")
    parser.add_argument("--manifests", nargs="+", default=None)
    parser.add_argument("--parallel", action="store_true")
    parser.add_argument("--confirm-paper", action="store_true")
    parser.add_argument("--confirm-live", action="store_true")
    parser.add_argument("--confirm-paper-trial", action="store_true")
    parser.add_argument(
        "--manifest",
        default=None,
        help="Path to trial manifest JSON file (overrides other trial flags)",
    )
    parser.add_argument("--archive-dir", default="archives/db")
    parser.add_argument("--keep-original", action="store_true")
    parser.add_argument("--rotate-suffix", default=None)
    parser.add_argument("--auto-rotate-paper-db", action="store_true")
    parser.add_argument("--no-auto-rotate-paper-db", action="store_true")
    return parser


def apply_common_settings(
    args: argparse.Namespace,
    settings: Settings,
    apply_runtime_profile: Callable[[Settings, str], None],
) -> None:
    """Apply common runtime/profile flags to settings before dispatch."""
    apply_runtime_profile(settings, args.profile)
    settings.strategy.name = args.strategy
    settings.initial_capital = args.capital
    if args.broker:
        settings.broker.provider = args.broker
    if args.no_market_hours:
        settings.enforce_market_hours = False
    if args.auto_rotate_paper_db:
        settings.auto_rotate_paper_db = True
    if args.no_auto_rotate_paper_db:
        settings.auto_rotate_paper_db = False
    if args.symbols:
        settings.data.symbols = args.symbols


def dispatch(
    args: argparse.Namespace,
    settings: Settings,
    *,
    handlers: dict[str, Callable[..., Any]],
    ibkr_broker_cls,
) -> None:
    """Dispatch parsed args to selected runtime mode.

    Notes:
    - `handlers` is injected from main to avoid circular imports.
    - Public behavior mirrors previous inline dispatch block.
    """
    mode = args.mode

    if mode == "backtest":
        handlers["cmd_backtest"](settings, args.start, args.end)

    elif mode == "walk_forward":
        handlers["cmd_walk_forward"](
            settings,
            args.start,
            args.end,
            args.train_months,
            args.test_months,
            args.step_months,
        )

    elif mode in ("paper", "live"):
        handlers["_require_explicit_confirmation"](
            mode,
            confirm_paper=args.confirm_paper,
            confirm_live=args.confirm_live,
            confirm_paper_trial=args.confirm_paper_trial,
        )
        if mode == "live":
            settings.broker.paper_trading = False
            if settings.broker.provider.lower() == "ibkr":
                confirm = input(
                    "\nWARNING: IBKR LIVE trading with real money.\n"
                    "Type 'yes ibkr live' to confirm: "
                )
                if confirm.strip().lower() != "yes ibkr live":
                    print("Aborted.")
                    raise SystemExit(0)
            else:
                confirm = input(
                    "\nWARNING: LIVE trading with real money.\n"
                    "Type 'yes I understand' to confirm: "
                )
                if confirm.strip().lower() != "yes i understand":
                    print("Aborted.")
                    raise SystemExit(0)
        else:
            settings.broker.paper_trading = True

        broker = None
        if settings.broker.provider.lower() == "ibkr":
            broker = ibkr_broker_cls(settings)
        try:
            asyncio.run(handlers["cmd_paper"](settings, broker=broker))
        finally:
            if broker is not None:
                broker.disconnect()

    elif mode == "uk_tax_export":
        export_db_path = args.db_path or handlers["resolve_runtime_db_path"](settings, "paper")
        handlers["cmd_uk_tax_export"](settings, export_db_path, args.output_dir)

    elif mode == "paper_session_summary":
        summary_db_path = args.db_path or handlers["resolve_runtime_db_path"](settings, "paper")
        handlers["cmd_paper_session_summary"](settings, summary_db_path, args.output_dir)

    elif mode == "paper_reconcile":
        if not args.expected_json:
            raise SystemExit("--expected-json is required for paper_reconcile mode")
        reconcile_db_path = args.db_path or handlers["resolve_runtime_db_path"](settings, "paper")
        drift_count = handlers["cmd_paper_reconcile"](
            settings,
            reconcile_db_path,
            args.output_dir,
            args.expected_json,
            args.tolerance_json,
        )
        if args.strict_reconcile and drift_count > 0:
            raise SystemExit(1)

    elif mode == "paper_trial":
        handlers["_require_explicit_confirmation"](
            mode,
            confirm_paper=args.confirm_paper,
            confirm_live=args.confirm_live,
            confirm_paper_trial=args.confirm_paper_trial,
        )
        if args.manifest:
            manifest = TrialManifest.from_json(args.manifest)
            handlers["logger"].info("Loaded trial manifest: %s", manifest.name)

            if manifest.profile:
                handlers["apply_runtime_profile"](settings, manifest.profile)
            if manifest.strategy:
                settings.strategy.name = manifest.strategy
            if manifest.symbols:
                settings.data.symbols = manifest.symbols
            if manifest.capital:
                settings.initial_capital = manifest.capital

            trial_db_path = manifest.db_path or handlers["resolve_runtime_db_path"](settings, "paper")
            exit_code = handlers["cmd_paper_trial"](
                settings,
                duration_seconds=manifest.duration_seconds,
                db_path=trial_db_path,
                output_dir=manifest.output_dir,
                expected_json_path=manifest.expected_json,
                tolerance_json_path=manifest.tolerance_json,
                strict_reconcile=manifest.strict_reconcile,
                skip_health_check=manifest.skip_health_check,
                skip_rotate=manifest.skip_rotate,
            )
        else:
            trial_db_path = args.db_path or handlers["resolve_runtime_db_path"](settings, "paper")
            exit_code = handlers["cmd_paper_trial"](
                settings,
                duration_seconds=args.paper_duration_seconds,
                db_path=trial_db_path,
                output_dir=args.output_dir,
                expected_json_path=args.expected_json,
                tolerance_json_path=args.tolerance_json,
                strict_reconcile=args.strict_reconcile,
                skip_health_check=args.skip_health_check,
                skip_rotate=args.skip_rotate,
            )
        if exit_code != 0:
            raise SystemExit(exit_code)

    elif mode == "trial_batch":
        handlers["_require_explicit_confirmation"](
            "paper_trial",
            confirm_paper=args.confirm_paper,
            confirm_live=args.confirm_live,
            confirm_paper_trial=args.confirm_paper_trial,
        )
        if not args.manifests:
            raise SystemExit("--manifests is required for trial_batch mode")
        handlers["cmd_trial_batch"](
            settings,
            manifest_patterns=args.manifests,
            output_dir=args.output_dir,
            parallel=args.parallel,
        )

    elif mode == "execution_dashboard":
        dashboard_db_path = args.db_path or handlers["resolve_runtime_db_path"](settings, "paper")
        dashboard_output = args.output or "reports/execution_dashboard.html"
        handlers["cmd_execution_dashboard"](
            settings,
            dashboard_db_path,
            dashboard_output,
            refresh_seconds=args.refresh_seconds,
        )

    elif mode == "data_quality_report":
        quality_db_path = args.db_path or handlers["resolve_runtime_db_path"](settings, "paper")
        quality_output = args.output or "reports/data_quality.json"
        handlers["cmd_data_quality_report"](
            settings,
            quality_db_path,
            quality_output,
            dashboard_path="reports/execution_dashboard.html",
        )

    elif mode == "daily_report":
        report_db_path = args.db_path or handlers["resolve_runtime_db_path"](settings, "paper")
        handlers["cmd_daily_report"](
            settings,
            report_db_path,
            output_dir=args.output_dir or "reports/daily",
            report_date=args.report_date,
            notify_email=args.notify_email,
        )

    elif mode == "promotion_checklist":
        checklist_output_dir = args.output_dir or "reports/promotions"
        handlers["cmd_promotion_checklist"](
            settings,
            strategy=settings.strategy.name,
            output_dir=checklist_output_dir,
            summary_json_path=args.summary_json,
            audit_db_path=args.audit_db_path,
        )

    elif mode == "research_register_candidate":
        if not args.candidate_dir:
            raise SystemExit("--candidate-dir is required for research_register_candidate mode")
        handlers["cmd_research_register_candidate"](
            settings,
            candidate_dir=args.candidate_dir,
            output_dir=args.output_dir,
            registry_db_path=args.registry_db_path,
            artifacts_dir=args.artifacts_dir,
            reviewer_1=args.reviewer_1,
            reviewer_2=args.reviewer_2,
        )

    elif mode == "research_train_xgboost":
        if args.print_presets:
            from research.experiments.presets import load_xgb_presets

            presets = load_xgb_presets(args.xgb_presets_path)
            print(json.dumps(presets, indent=2))
            raise SystemExit(0)

        config = None
        if args.config:
            from research.experiments.config import load_experiment_config

            config = load_experiment_config(args.config)

        if config is None:
            if not args.snapshot_dir:
                raise SystemExit("--snapshot-dir is required for research_train_xgboost mode")
            if not args.experiment_id:
                raise SystemExit("--experiment-id is required for research_train_xgboost mode")
            if not args.symbols or len(args.symbols) != 1:
                raise SystemExit("--symbols must include exactly one symbol for research_train_xgboost")

        params = None
        if args.xgb_params_json:
            params_path = Path(args.xgb_params_json)
            params = json.loads(params_path.read_text(encoding="utf-8"))

        from research.experiments.presets import resolve_xgb_params

        preset_name = config.xgb_preset if config else args.xgb_preset
        preset_path = args.xgb_presets_path
        resolved_params = resolve_xgb_params(
            preset_name=preset_name,
            explicit_params=config.xgb_params if config else params,
            presets_path=preset_path,
        )

        if args.dry_run:
            resolved_config = {
                "snapshot_dir": config.snapshot_dir if config else args.snapshot_dir,
                "experiment_id": config.experiment_id if config else args.experiment_id,
                "symbol": config.symbol if config else args.symbols[0],
                "output_dir": config.output_dir if config else args.output_dir,
                "horizon_days": config.horizon_days if config else args.horizon_days,
                "train_ratio": config.train_ratio if config else args.train_ratio,
                "val_ratio": config.val_ratio if config else args.val_ratio,
                "gap_days": config.gap_days if config else args.gap_days,
                "feature_version": config.feature_version if config else args.feature_version,
                "label_version": config.label_version if config else args.label_version,
                "model_id": config.model_id if config else args.model_id,
                "xgb_params": resolved_params,
                "calibrate": config.calibrate if config else args.calibrate,
            }
            print(json.dumps(resolved_config, indent=2))
            raise SystemExit(0)

        from research.experiments.xgboost_pipeline import run_xgboost_experiment

        result = run_xgboost_experiment(
            snapshot_dir=config.snapshot_dir if config else args.snapshot_dir,
            experiment_id=config.experiment_id if config else args.experiment_id,
            symbol=config.symbol if config else args.symbols[0],
            output_dir=config.output_dir if config else args.output_dir,
            horizon_days=config.horizon_days if config else args.horizon_days,
            train_ratio=config.train_ratio if config else args.train_ratio,
            val_ratio=config.val_ratio if config else args.val_ratio,
            gap_days=config.gap_days if config else args.gap_days,
            feature_version=config.feature_version if config else args.feature_version,
            label_version=config.label_version if config else args.label_version,
            model_id=config.model_id if config else args.model_id,
            model_params=resolved_params,
            calibrate=config.calibrate if config else args.calibrate,
            walk_forward=config.walk_forward if config else args.walk_forward,
            train_months=config.train_months if config else args.train_months,
            val_months=config.val_months if config else args.val_months,
            test_months=config.test_months if config else args.test_months,
            step_months=config.step_months if config else args.step_months,
        )

        handlers["logger"].info("XGBoost experiment complete: %s", result.training_report_path)

    elif mode == "research_download_ticks":
        if not args.symbols or len(args.symbols) != 1:
            raise SystemExit("--symbols must include exactly one symbol for research_download_ticks")
        if not args.tick_date and not (args.tick_start_date and args.tick_end_date):
            raise SystemExit("Provide --tick-date or both --tick-start-date and --tick-end-date")

        symbol = args.symbols[0]
        if args.tick_provider != "polygon":
            raise SystemExit(f"Unsupported tick provider: {args.tick_provider}")

        from research.data.tick_download import (
            convert_polygon_json_to_tick_csv,
            download_polygon_trades_json,
            download_polygon_trades_range,
        )

        if args.tick_date:
            json_paths = [
                download_polygon_trades_json(
                    symbol=symbol,
                    trade_date=args.tick_date,
                    output_dir=args.tick_output_dir,
                    api_key=args.tick_api_key,
                    limit=args.tick_limit,
                    max_pages=args.tick_max_pages,
                )
            ]
        else:
            json_paths = download_polygon_trades_range(
                symbol=symbol,
                start_date=args.tick_start_date,
                end_date=args.tick_end_date,
                output_dir=args.tick_output_dir,
                api_key=args.tick_api_key,
                limit=args.tick_limit,
                max_pages=args.tick_max_pages,
            )

        for json_path in json_paths:
            trade_date = json_path.stem.split("_")[-1]
            csv_path = Path(args.tick_output_dir) / f"polygon_{symbol}_{trade_date}.csv"
            convert_polygon_json_to_tick_csv(json_path, output_csv=csv_path, symbol_override=symbol)
            handlers["logger"].info("Downloaded Polygon ticks JSON: %s", json_path)
            handlers["logger"].info("Converted canonical tick CSV: %s", csv_path)

        if args.tick_build_manifest:
            from research.data.tick_backlog import build_tick_backlog_manifest

            manifest_path = (
                Path(args.tick_manifest_path)
                if args.tick_manifest_path
                else Path(args.tick_output_dir) / "tick_backlog_manifest.json"
            )
            result = build_tick_backlog_manifest(
                data_dir=args.tick_output_dir,
                output_path=manifest_path,
            )
            handlers["logger"].info("Tick backlog manifest written: %s", result)

    elif mode == "research_build_tick_splits":
        if not args.tick_input_manifest:
            raise SystemExit("--tick-input-manifest is required for research_build_tick_splits mode")
        if not args.tick_train_end or not args.tick_val_end:
            raise SystemExit("--tick-train-end and --tick-val-end are required")

        symbol = args.symbols[0] if args.symbols and len(args.symbols) == 1 else None
        from research.data.tick_bundle import build_tick_split_bundles

        outputs = build_tick_split_bundles(
            manifest_path=args.tick_input_manifest,
            output_dir=args.tick_split_output_dir,
            symbol=symbol,
            start_date=args.tick_start_date,
            end_date=args.tick_end_date,
            train_end=args.tick_train_end,
            val_end=args.tick_val_end,
        )

        handlers["logger"].info("Tick split bundle (train): %s", outputs["train"])
        handlers["logger"].info("Tick split bundle (val): %s", outputs["val"])
        handlers["logger"].info("Tick split bundle (test): %s", outputs["test"])
        handlers["logger"].info("Tick split summary: %s", outputs["summary"])

    elif mode == "research_ingest_flat_files":
        if not args.symbols:
            raise SystemExit("--symbols is required for research_ingest_flat_files")
        if not args.start or not args.end:
            raise SystemExit("--start and --end are required for research_ingest_flat_files")

        from research.data.flat_file_ingestion import ingest_flat_files

        result = ingest_flat_files(
            symbols=args.symbols,
            start=args.start,
            end=args.end,
            output_dir=args.flat_output_dir,
            manifest_path=args.flat_manifest_path,
            skip_existing=args.flat_skip_existing,
        )
        handlers["logger"].info("Flat file ingestion completed")
        handlers["logger"].info("  manifest: %s", result.manifest_path)
        handlers["logger"].info("  files: %s", result.file_count)
        handlers["logger"].info("  rows: %s", result.total_rows)

    elif mode == "uk_health_check":
        error_count = handlers["cmd_uk_health_check"](
            settings,
            with_data_check=args.with_data_check,
            json_output=args.health_json,
        )
        if args.strict_health and error_count > 0:
            raise SystemExit(1)

    elif mode == "rotate_paper_db":
        handlers["cmd_rotate_paper_db"](
            settings,
            archive_dir=args.archive_dir,
            keep_original=args.keep_original,
            suffix=args.rotate_suffix,
        )
