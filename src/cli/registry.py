"""Command handler registry for the trading bot CLI.

Functions decorated with ``@command("mode_name")`` are registered here and
looked up by :func:`src.cli.arguments.dispatch` without requiring the caller
to pass a handler dictionary.

Usage example::

    from src.cli.registry import command

    @command("backtest")
    def cmd_backtest(settings, start, end):
        ...
"""

from __future__ import annotations

from typing import Any, Callable

_REGISTRY: dict[str, Any] = {}


def command(name: str) -> Callable:
    """Register a handler function under the given name.

    Args:
        name: Registry key (a CLI mode name or utility function name).

    Returns:
        Decorator that registers and returns the function unchanged.
    """

    def decorator(fn: Callable) -> Callable:
        _REGISTRY[name] = fn
        return fn

    return decorator


def get_registry() -> dict[str, Any]:
    """Return the current handler registry.

    Returns:
        Mapping of handler name to registered callable.
    """
    return _REGISTRY
