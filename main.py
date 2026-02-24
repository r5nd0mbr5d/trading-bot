"""Trading Bot CLI entry point."""

from config.settings import Settings
from src.cli.arguments import apply_common_settings, build_argument_parser, dispatch
from src.cli.runtime import (
    STRATEGIES,
    _require_explicit_confirmation,
    apply_runtime_profile,
    cmd_backtest,
    cmd_daily_report,
    cmd_data_quality_report,
    cmd_execution_dashboard,
    cmd_paper,
    cmd_paper_reconcile,
    cmd_paper_session_summary,
    cmd_paper_trial,
    cmd_promotion_checklist,
    cmd_research_register_candidate,
    cmd_rotate_paper_db,
    cmd_trial_batch,
    cmd_uk_health_check,
    cmd_uk_tax_export,
    cmd_walk_forward,
    logger,
    resolve_runtime_db_path,
)
from src.execution.ibkr_broker import IBKRBroker


if __name__ == "__main__":
    parser = build_argument_parser(STRATEGIES.keys())
    args = parser.parse_args()

    settings = Settings()
    apply_common_settings(args, settings, apply_runtime_profile)

    dispatch(
        args,
        settings,
        handlers={
            "logger": logger,
            "apply_runtime_profile": apply_runtime_profile,
            "resolve_runtime_db_path": resolve_runtime_db_path,
            "_require_explicit_confirmation": _require_explicit_confirmation,
            "cmd_backtest": cmd_backtest,
            "cmd_walk_forward": cmd_walk_forward,
            "cmd_paper": cmd_paper,
            "cmd_uk_tax_export": cmd_uk_tax_export,
            "cmd_paper_session_summary": cmd_paper_session_summary,
            "cmd_paper_reconcile": cmd_paper_reconcile,
            "cmd_paper_trial": cmd_paper_trial,
            "cmd_trial_batch": cmd_trial_batch,
            "cmd_execution_dashboard": cmd_execution_dashboard,
            "cmd_data_quality_report": cmd_data_quality_report,
            "cmd_daily_report": cmd_daily_report,
            "cmd_promotion_checklist": cmd_promotion_checklist,
            "cmd_research_register_candidate": cmd_research_register_candidate,
            "cmd_uk_health_check": cmd_uk_health_check,
            "cmd_rotate_paper_db": cmd_rotate_paper_db,
        },
        ibkr_broker_cls=IBKRBroker,
    )
