"""In-memory latest-price cache."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timezone

from app.market.models import PriceQuote


class PriceCache:
    def __init__(self, stale_after_seconds: float) -> None:
        self._quotes: dict[str, PriceQuote] = {}
        self._stale_after_seconds = stale_after_seconds
        self._lock = asyncio.Lock()

    async def snapshot(self) -> dict[str, PriceQuote]:
        async with self._lock:
            return {ticker: self._mark_stale(quote) for ticker, quote in self._quotes.items()}

    async def get(self, ticker: str) -> PriceQuote | None:
        async with self._lock:
            quote = self._quotes.get(ticker.strip().upper())
            return self._mark_stale(quote) if quote else None

    async def update_many(self, quotes: dict[str, PriceQuote]) -> None:
        async with self._lock:
            for ticker, quote in quotes.items():
                symbol = ticker.strip().upper()
                if not symbol or quote.price <= 0:
                    continue
                previous = self._quotes.get(symbol)
                previous_price = previous.price if previous else quote.previous_price
                self._quotes[symbol] = quote.with_previous_price(previous_price)

    def _mark_stale(self, quote: PriceQuote) -> PriceQuote:
        if quote.timestamp.tzinfo is None:
            timestamp = quote.timestamp.replace(tzinfo=timezone.utc)
        else:
            timestamp = quote.timestamp.astimezone(timezone.utc)
        age = (datetime.now(timezone.utc) - timestamp).total_seconds()
        if age <= self._stale_after_seconds and not quote.stale:
            return quote
        return replace(quote, stale=True, timestamp=timestamp)
