"""Market data background refresh service."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable

from app.market.cache import PriceCache
from app.market.models import MarketProviderHealth
from app.market.provider import MarketDataProvider
from app.market.validation import normalize_ticker_set


DEFAULT_WATCHLIST_TICKERS = {
    "AAPL",
    "GOOGL",
    "MSFT",
    "AMZN",
    "TSLA",
    "NVDA",
    "META",
    "JPM",
    "V",
    "NFLX",
}

TickerLoader = Callable[[], Awaitable[set[str]]]


async def default_ticker_loader() -> set[str]:
    return set(DEFAULT_WATCHLIST_TICKERS)


class MarketDataService:
    def __init__(
        self,
        provider: MarketDataProvider,
        cache: PriceCache,
        ticker_loader: TickerLoader = default_ticker_loader,
        poll_interval_seconds: float = 0.5,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")
        self.provider = provider
        self.cache = cache
        self.ticker_loader = ticker_loader
        self.poll_interval_seconds = poll_interval_seconds
        self._tickers: set[str] = set()
        self._extra_tickers: set[str] = set()
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._task is not None:
            return
        await self.refresh_tracked_tickers()
        await self.refresh_once()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def refresh_tracked_tickers(self) -> None:
        loaded = await self.ticker_loader()
        async with self._lock:
            self._tickers = normalize_ticker_set(loaded) | set(self._extra_tickers)

    async def add_tracked_ticker(self, ticker: str) -> None:
        normalized = normalize_ticker_set({ticker})
        if not normalized:
            return
        async with self._lock:
            self._extra_tickers.update(normalized)
            self._tickers.update(normalized)

    async def tracked_tickers(self) -> set[str]:
        async with self._lock:
            return set(self._tickers)

    async def refresh_once(self) -> None:
        async with self._lock:
            tickers = set(self._tickers)
        if not tickers:
            return
        quotes = await self.provider.get_prices(tickers)
        await self.cache.update_many(quotes)

    def health(self) -> MarketProviderHealth:
        return self.provider.health()

    async def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await self.refresh_tracked_tickers()
                await self.refresh_once()
            except Exception:
                pass
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.poll_interval_seconds)
            except TimeoutError:
                continue
