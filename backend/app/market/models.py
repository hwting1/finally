"""Provider-independent market data values."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class MarketSource(StrEnum):
    """Origin of a market data value."""

    MASSIVE = "massive"
    SIMULATOR = "simulator"


class MarketSession(StrEnum):
    """Trading session represented by a quote."""

    OPEN = "open"
    CLOSED = "closed"
    PREMARKET = "premarket"
    AFTER_HOURS = "after_hours"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class PriceQuote:
    """A normalized latest price returned by any provider."""

    ticker: str
    price: float
    previous_price: float | None
    previous_close: float | None
    timestamp: datetime
    source: MarketSource
    session: MarketSession = MarketSession.UNKNOWN
    stale: bool = False
    volume: float | None = None
    day_open: float | None = None
    day_high: float | None = None
    day_low: float | None = None

    @property
    def change(self) -> float | None:
        if self.previous_close is None:
            return None
        return self.price - self.previous_close

    @property
    def change_percent(self) -> float | None:
        if self.previous_close in (None, 0):
            return None
        return (self.price - self.previous_close) / self.previous_close * 100

    @property
    def direction(self) -> str:
        if self.previous_price is None or self.price == self.previous_price:
            return "flat"
        return "up" if self.price > self.previous_price else "down"


@dataclass(frozen=True, slots=True)
class DailyBar:
    """A normalized end-of-day OHLCV bar."""

    ticker: str
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float | None
    vwap: float | None
    source: MarketSource
    adjusted: bool = True


@dataclass(frozen=True, slots=True)
class MarketProviderHealth:
    """Current provider status without additional I/O."""

    source: MarketSource
    ok: bool
    message: str | None = None
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
