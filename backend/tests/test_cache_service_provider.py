import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.market.cache import PriceCache
from app.market.models import MarketProviderHealth, MarketSession, MarketSource, PriceQuote
from app.market.provider import create_market_provider, default_poll_interval_seconds
from app.market.service import MarketDataService
from app.market.simulator import SimulatedMarketDataProvider


NOW = datetime(2026, 7, 30, 12, tzinfo=timezone.utc)


@dataclass
class Settings:
    massive_api_key: str = ""
    market_poll_interval_seconds: float | None = None
    market_stale_after_seconds: float = 30.0
    market_simulator_seed: int = 42


class RecordingProvider:
    def __init__(self) -> None:
        self.calls: list[set[str]] = []

    async def get_prices(self, tickers: set[str]) -> dict[str, PriceQuote]:
        self.calls.append(set(tickers))
        return {
            ticker: PriceQuote(
                ticker=ticker,
                price=100.0 + len(self.calls),
                previous_price=None,
                previous_close=100.0,
                timestamp=NOW,
                source=MarketSource.SIMULATOR,
                session=MarketSession.OPEN,
            )
            for ticker in tickers
        }

    async def get_previous_day_bars(self, tickers: set[str]) -> dict:
        return {}

    def health(self) -> MarketProviderHealth:
        return MarketProviderHealth(source=MarketSource.SIMULATOR, ok=True)


def run(awaitable):
    return asyncio.run(awaitable)


def quote(ticker: str, price: float, timestamp: datetime = NOW) -> PriceQuote:
    return PriceQuote(
        ticker=ticker,
        price=price,
        previous_price=None,
        previous_close=100.0,
        timestamp=timestamp,
        source=MarketSource.SIMULATOR,
        session=MarketSession.OPEN,
    )


def test_provider_factory_selects_simulator_without_massive_key() -> None:
    provider = create_market_provider(Settings())
    assert isinstance(provider, SimulatedMarketDataProvider)
    assert default_poll_interval_seconds(Settings()) == 0.5


def test_provider_factory_selects_massive_with_key() -> None:
    provider = create_market_provider(Settings(massive_api_key=" key "))
    assert provider.health().source is MarketSource.MASSIVE
    assert default_poll_interval_seconds(Settings(massive_api_key="key")) == 15.0
    assert default_poll_interval_seconds(
        Settings(massive_api_key="key", market_poll_interval_seconds=2.0)
    ) == 2.0


def test_cache_preserves_previous_price_and_marks_stale() -> None:
    cache = PriceCache(stale_after_seconds=1.0)
    run(cache.update_many({"AAPL": quote("AAPL", 100.0)}))
    run(cache.update_many({"AAPL": quote("AAPL", 101.0)}))

    current = run(cache.get("aapl"))

    assert current is not None
    assert current.previous_price == 100.0
    assert current.direction == "up"

    run(cache.update_many({"MSFT": quote("MSFT", 200.0, NOW - timedelta(seconds=60))}))
    stale = run(cache.get("MSFT"))
    assert stale is not None
    assert stale.stale is True


def test_cache_drops_invalid_zero_prices() -> None:
    cache = PriceCache(stale_after_seconds=30.0)
    run(cache.update_many({"AAPL": quote("AAPL", 0.0)}))
    assert run(cache.get("AAPL")) is None


def test_market_service_tracks_loader_union_and_refreshes_cache() -> None:
    provider = RecordingProvider()
    cache = PriceCache(stale_after_seconds=30.0)

    async def loader() -> set[str]:
        return {" aapl ", "MSFT"}

    service = MarketDataService(provider, cache, loader, poll_interval_seconds=0.5)

    run(service.refresh_tracked_tickers())
    run(service.add_tracked_ticker("nvda"))
    run(service.refresh_once())

    assert provider.calls == [{"AAPL", "MSFT", "NVDA"}]
    assert run(cache.get("AAPL")) is not None
    assert run(cache.get("NVDA")) is not None


def test_market_service_preserves_added_tickers_and_filters_invalid_symbols() -> None:
    provider = RecordingProvider()
    cache = PriceCache(stale_after_seconds=30.0)

    async def loader() -> set[str]:
        return {"AAPL", "TOOLONG", "BAD!"}

    service = MarketDataService(provider, cache, loader, poll_interval_seconds=0.5)

    run(service.refresh_tracked_tickers())
    run(service.add_tracked_ticker("nvda"))
    run(service.add_tracked_ticker("no-good"))
    run(service.refresh_tracked_tickers())
    run(service.refresh_once())

    assert provider.calls == [{"AAPL", "NVDA"}]
