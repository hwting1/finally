"""Contract implemented by every market data provider."""

from __future__ import annotations

from typing import Protocol

from app.market.models import DailyBar, MarketProviderHealth, PriceQuote


class MarketDataProvider(Protocol):
    async def get_prices(self, tickers: set[str]) -> dict[str, PriceQuote]:
        """Return latest normalized prices keyed by uppercase ticker."""
        ...

    async def get_previous_day_bars(self, tickers: set[str]) -> dict[str, DailyBar]:
        """Return previous trading-day bars keyed by uppercase ticker."""
        ...

    def health(self) -> MarketProviderHealth:
        """Return provider status without performing network I/O."""
        ...
