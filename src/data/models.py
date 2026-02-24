"""Core data structures shared across all modules."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class SignalType(str, Enum):
    LONG = "long"  # Enter a long position
    SHORT = "short"  # Enter a short position (not yet implemented)
    CLOSE = "close"  # Exit the current position
    HOLD = "hold"  # No action


@dataclass
class Bar:
    """A single OHLCV price bar."""

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def typical_price(self) -> float:
        return (self.high + self.low + self.close) / 3


@dataclass
class Signal:
    """A trading signal produced by a strategy."""

    symbol: str
    signal_type: SignalType
    strength: float  # 0.0 (weak) to 1.0 (strong) — used for position sizing
    timestamp: datetime
    strategy_name: str
    metadata: dict = field(default_factory=dict)


@dataclass
class Order:
    """An order sent to the broker."""

    symbol: str
    side: OrderSide
    qty: float
    order_id: str = ""
    status: OrderStatus = OrderStatus.PENDING
    filled_price: Optional[float] = None
    filled_at: Optional[datetime] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@dataclass
class Position:
    """An open position in the portfolio."""

    symbol: str
    qty: float
    avg_entry_price: float
    current_price: float

    @property
    def market_value(self) -> float:
        return self.qty * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        return self.qty * (self.current_price - self.avg_entry_price)

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.avg_entry_price == 0:
            return 0.0
        return (self.current_price - self.avg_entry_price) / self.avg_entry_price
