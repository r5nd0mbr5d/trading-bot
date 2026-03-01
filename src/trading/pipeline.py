"""Composable bar-processing pipeline with event hooks.

``BarPipeline`` wraps a :class:`~src.trading.loop.TradingLoopHandler` and
exposes callback hooks so external observers (e.g. monitoring agents, PAIOS
integration) can react to key pipeline events without modifying business logic.

Usage::

    from src.trading.pipeline import BarPipeline
    from src.trading.loop import TradingLoopHandler

    handler = TradingLoopHandler(...)
    pipeline = BarPipeline(handler)

    pipeline.on_bar_received = lambda bar: print("bar:", bar.symbol)
    pipeline.on_signal_generated = lambda sig: print("signal:", sig.signal_type)

    # Replace handler.on_bar with pipeline.process in feed.stream(...)
    await feed.stream(symbols, pipeline.process, ...)
"""

from __future__ import annotations

from typing import Callable, Optional

from src.data.models import Bar, Order, Signal
from src.trading.loop import TradingLoopHandler


class BarPipeline:
    """Composable wrapper around :class:`TradingLoopHandler` with event hooks.

    Each bar flows through the same stages as before
    (DataQualityGuard → Strategy → RiskManager → Broker → AuditLog → Portfolio),
    but the pipeline fires optional callbacks at key transition points so that
    external observers can react without coupling to internal handler methods.

    Attributes:
        on_bar_received: Called with ``Bar`` before processing begins.
        on_signal_generated: Called with ``Signal`` when strategy emits a signal.
        on_order_submitted: Called with ``Order`` when an order is sent to the broker.
        on_fill_received: Called with the filled ``Order`` on a successful fill.
    """

    def __init__(self, handler: TradingLoopHandler) -> None:
        """Wrap an existing handler with hook support.

        Args:
            handler: Fully initialised :class:`TradingLoopHandler` instance.
        """
        self._handler = handler
        self.on_bar_received: Optional[Callable[[Bar], None]] = None
        self.on_signal_generated: Optional[Callable[[Signal], None]] = None
        self.on_order_submitted: Optional[Callable[[Order], None]] = None
        self.on_fill_received: Optional[Callable[[Order], None]] = None
        # Wire hooks into the handler so deeper events can be observed.
        handler._on_signal_generated = self._fire_signal_generated
        handler._on_order_submitted = self._fire_order_submitted
        handler._on_fill_received = self._fire_fill_received

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def process(self, bar: Bar) -> None:
        """Process a bar through the full pipeline.

        Fires ``on_bar_received`` then delegates to the handler's bar loop,
        which in turn fires the remaining hooks at the appropriate points.

        Args:
            bar: OHLCV bar with UTC timestamp.
        """
        if self.on_bar_received:
            self.on_bar_received(bar)
        self._handler.on_bar(bar)

    # ------------------------------------------------------------------
    # Internal callbacks wired into TradingLoopHandler
    # ------------------------------------------------------------------

    def _fire_signal_generated(self, signal: Signal) -> None:
        if self.on_signal_generated:
            self.on_signal_generated(signal)

    def _fire_order_submitted(self, order: Order) -> None:
        if self.on_order_submitted:
            self.on_order_submitted(order)

    def _fire_fill_received(self, order: Order) -> None:
        if self.on_fill_received:
            self.on_fill_received(order)
