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


class MarketSettings(Protocol):
    massive_api_key: str
    market_poll_interval_seconds: float | None
    market_stale_after_seconds: float
    market_simulator_seed: int


def create_market_provider(settings: MarketSettings) -> MarketDataProvider:
    api_key = settings.massive_api_key.strip()
    if api_key:
        from app.market.massive import MassiveMarketDataProvider

        return MassiveMarketDataProvider(
            api_key=api_key,
            stale_after_seconds=settings.market_stale_after_seconds,
        )

    from app.market.simulator import SimulatedMarketDataProvider

    return SimulatedMarketDataProvider(seed=settings.market_simulator_seed)


def default_poll_interval_seconds(settings: MarketSettings) -> float:
    if settings.market_poll_interval_seconds is not None:
        return settings.market_poll_interval_seconds
    if settings.massive_api_key.strip():
        return 15.0
    return 0.5
