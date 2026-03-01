"""Trading Bot CLI entry point."""

from config.settings import Settings
from src.cli.arguments import apply_common_settings, build_argument_parser, dispatch
from src.cli.runtime import STRATEGIES, apply_runtime_profile
from src.execution.ibkr_broker import IBKRBroker


if __name__ == "__main__":
    parser = build_argument_parser(STRATEGIES.keys())
    args = parser.parse_args()

    settings = Settings()
    apply_common_settings(args, settings, apply_runtime_profile)

    dispatch(args, settings, ibkr_broker_cls=IBKRBroker)
