# Market Data Interface

FinAlly uses one Python market-data interface with two implementations:

- `MassiveMarketDataProvider` when `MASSIVE_API_KEY` is set and non-empty.
- `SimulatedMarketDataProvider` when `MASSIVE_API_KEY` is absent or empty.

Downstream backend code must not branch on the provider. SSE streaming, order filling, portfolio valuation, LLM tools, and tests should consume the same typed objects from either provider.

Related docs:

- Massive REST research: `planning/MASSIVE_API.md`
- Simulator design: `planning/MARKET_SIMULATOR.md`
- Project architecture: `planning/PLAN.md`

## Goals

- Keep real market data optional.
- Keep the simulator deterministic enough for tests and demos.
- Support multi-ticker polling in a single provider call.
- Expose stale/closed-market state explicitly.
- Make market orders fill against the exact same cached price that the UI shows.
- Preserve a clean extension point for future WebSockets or alternative data vendors.

## Suggested Backend Modules

```text
backend/
  app/
    market/
      __init__.py
      models.py
      provider.py
      massive.py
      simulator.py
      cache.py
      service.py
```

Responsibilities:

| Module | Responsibility |
|---|---|
| `models.py` | Dataclasses or Pydantic models shared by market providers |
| `provider.py` | Abstract base class / Protocol for market data providers |
| `massive.py` | REST adapter for Massive snapshots and EOD aggregate bars |
| `simulator.py` | Deterministic simulated price engine |
| `cache.py` | In-memory latest-price cache with stale metadata |
| `service.py` | Provider selection, background task orchestration, ticker universe management |

## Domain Models

Use one normalized quote object for UI streaming and trade fills.

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class MarketSource(StrEnum):
    MASSIVE = "massive"
    SIMULATOR = "simulator"


class MarketSession(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    PREMARKET = "premarket"
    AFTER_HOURS = "after_hours"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class PriceQuote:
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
        baseline = self.previous_close
        if baseline is None:
            return None
        return self.price - baseline

    @property
    def change_percent(self) -> float | None:
        baseline = self.previous_close
        if baseline in (None, 0):
            return None
        return (self.price - baseline) / baseline * 100

    @property
    def direction(self) -> str:
        if self.previous_price is None or self.price == self.previous_price:
            return "flat"
        return "up" if self.price > self.previous_price else "down"
```

Use a separate daily bar object for historical/EOD needs.

```python
@dataclass(frozen=True, slots=True)
class DailyBar:
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
```

Use one health object for diagnostics and UI/API status.

```python
@dataclass(frozen=True, slots=True)
class MarketProviderHealth:
    source: MarketSource
    ok: bool
    message: str | None = None
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
```

## Provider Protocol

```python
from __future__ import annotations

from typing import Protocol


class MarketDataProvider(Protocol):
    async def get_prices(self, tickers: set[str]) -> dict[str, PriceQuote]:
        """Return latest normalized prices keyed by uppercase ticker."""

    async def get_previous_day_bars(self, tickers: set[str]) -> dict[str, DailyBar]:
        """Return previous trading-day OHLCV bars keyed by uppercase ticker."""

    def health(self) -> MarketProviderHealth:
        """Return provider status without performing network I/O."""
```

Notes:

- `get_prices()` must batch tickers when the provider supports batching.
- Providers should normalize tickers to uppercase and remove duplicates.
- Missing symbols should simply be absent from the returned dict unless the provider has a useful explicit error model.
- The cache/service layer owns preserving old values for missing symbols.

## Provider Selection

Selection happens once at backend startup.

```python
import os


def create_market_provider() -> MarketDataProvider:
    api_key = os.getenv("MASSIVE_API_KEY", "").strip()
    if api_key:
        return MassiveMarketDataProvider(api_key=api_key)
    return SimulatedMarketDataProvider()
```

Do not fallback from Massive to simulator after startup. If a user sets `MASSIVE_API_KEY`, they are asking for real data. A bad key should produce a clear degraded provider state rather than a plausible but fake market.

## Massive Adapter Contract

`MassiveMarketDataProvider.get_prices()` should call:

```text
GET https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,MSFT,NVDA
```

Map the response according to `planning/MASSIVE_API.md`:

- Prefer `lastTrade.p`.
- Use quote midpoint from `lastQuote.p` bid and `lastQuote.P` ask as fallback.
- Use `min.c`, then `day.c`, then stale `prevDay.c`.
- Use `prevDay.c` as `previous_close`.
- Convert all timestamps to timezone-aware UTC datetimes.
- Set `source="massive"`.
- Set `stale=true` when using `prevDay.c`, when the selected timestamp is older than the configured stale threshold, or when the provider is in backoff and the cache is serving old data.

`MassiveMarketDataProvider.get_previous_day_bars()` may either:

- Use `prevDay` included in the snapshot result when the caller already has fresh snapshot data.
- Call `/v2/aggs/ticker/{stocksTicker}/prev?adjusted=true` per ticker for explicit EOD retrieval.

For many tickers on a known trading date, add a future method that calls grouped daily bars:

```text
GET /v2/aggs/grouped/locale/us/market/stocks/{date}
```

## Cache Contract

The cache is the single source of truth for current prices inside the backend.

```python
class PriceCache:
    def snapshot(self) -> dict[str, PriceQuote]:
        ...

    def get(self, ticker: str) -> PriceQuote | None:
        ...

    def update_many(self, quotes: dict[str, PriceQuote]) -> None:
        ...
```

Cache behavior:

- Preserve previous price when updating a ticker so `direction` and price flash state are consistent.
- Never return mutable provider internals.
- Keep prices for position tickers even if they are removed from the watchlist.
- Mark entries stale if their timestamp or provider health exceeds the stale threshold.
- Expose no-price state separately from zero price. A stock price of `0` should be treated as invalid.

## Market Service

The market service owns the ticker universe and the background update loop.

```python
class MarketDataService:
    def __init__(
        self,
        provider: MarketDataProvider,
        cache: PriceCache,
        poll_interval_seconds: float,
    ) -> None:
        self.provider = provider
        self.cache = cache
        self.poll_interval_seconds = poll_interval_seconds
        self._tickers: set[str] = set()

    def set_tracked_tickers(self, tickers: set[str]) -> None:
        self._tickers = {ticker.upper() for ticker in tickers}

    async def refresh_once(self) -> None:
        quotes = await self.provider.get_prices(self._tickers)
        self.cache.update_many(quotes)

    async def run_forever(self) -> None:
        while True:
            await self.refresh_once()
            await asyncio.sleep(self.poll_interval_seconds)
```

Recommended intervals:

| Provider | Poll interval | SSE publish cadence |
|---|---:|---:|
| Simulator | 0.5 seconds | 0.5 seconds |
| Massive REST free-safe default | 15 seconds | 0.5-1.0 seconds |
| Massive REST paid/manual override | 2-15 seconds | 0.5-1.0 seconds |

The SSE layer should publish from cache. It should not call providers directly.

## API Payload Shape

The SSE stream should use the same shape from `planning/PLAN.md`, backed by `PriceQuote`.

```json
{
  "type": "prices",
  "timestamp": "2026-07-30T12:00:00Z",
  "prices": [
    {
      "ticker": "AAPL",
      "price": 190.12,
      "previous_price": 189.88,
      "change": 0.24,
      "change_percent": 0.1264,
      "direction": "up",
      "stale": false,
      "source": "massive",
      "session": "open"
    }
  ]
}
```

REST endpoints that need current prices should read from cache:

- `GET /api/prices`
- `GET /api/prices/{ticker}`
- Trade execution logic for market orders
- Portfolio valuation endpoints
- LLM tool context

## Testing Requirements

Provider tests:

- Massive response mapping from fixture JSON.
- Price fallback order: trade, quote midpoint, minute close, day close, previous close.
- Timestamp conversion for nanosecond and millisecond fields.
- Empty/missing ticker responses.
- 401/403 provider health behavior.
- 429 backoff behavior.

Service tests:

- Provider selection with and without `MASSIVE_API_KEY`.
- Cache preserves previous price.
- Ticker universe is watchlist union positions.
- Market orders fill from cache, not by making a fresh provider call.

Simulator tests are detailed in `planning/MARKET_SIMULATOR.md`.

