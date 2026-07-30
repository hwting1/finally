# Market Data Backend Design

This document is the implementation blueprint for FinAlly's market data backend. It consolidates the project plan, unified interface, simulator, and Massive REST research into one buildable design.

Related planning files:

- `planning/PLAN.md`
- `planning/MARKET_INTERFACE.md`
- `planning/MARKET_SIMULATOR.md`
- `planning/MASSIVE_API.md`

## Objectives

- Run with no external services by default using deterministic simulated prices.
- Use Massive REST market data only when `MASSIVE_API_KEY` is configured.
- Expose one normalized quote contract to SSE, watchlist APIs, portfolio valuation, market order fills, and LLM context.
- Keep provider-specific behavior isolated behind a `MarketDataProvider` protocol.
- Make the in-memory price cache the single source of truth for current backend prices.
- Never silently switch from Massive to simulated data after startup.

## Non-Objectives

- No WebSockets for market data providers.
- No order book, bid/ask execution, partial fills, fees, dividends, splits, or backtesting.
- No persistent simulated market state in SQLite.
- No implicit live data fetches when simulator mode is selected.

## Module Layout

Create the market package inside the backend application:

```text
backend/
  app/
    core/
      config.py
    market/
      __init__.py
      models.py
      provider.py
      simulator.py
      massive.py
      cache.py
      service.py
      serialization.py
    api/
      market.py
      stream.py
```

Responsibilities:

| Module | Responsibility |
|---|---|
| `models.py` | Market enums and domain dataclasses |
| `provider.py` | Provider protocol and provider factory |
| `simulator.py` | Deterministic simulated market provider |
| `massive.py` | Massive REST adapter and response mapping |
| `cache.py` | Thread-safe in-memory latest price cache |
| `service.py` | Background refresh loop and tracked ticker universe |
| `serialization.py` | Convert domain objects into API/SSE payloads |
| `api/market.py` | Optional REST diagnostics for latest prices and provider status |
| `api/stream.py` | SSE price stream endpoint |

The package should be importable without requiring a Massive API key or network access. Massive network calls occur only inside `MassiveMarketDataProvider` methods.

## Configuration

Extend the backend settings object with market data settings. Keep environment parsing centralized so providers receive typed values instead of reading environment variables directly.

```python
# backend/app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    massive_api_key: str = ""
    market_poll_interval_seconds: float | None = None
    market_stale_after_seconds: float = 30.0
    market_simulator_seed: int = 42


settings = Settings()
```

Provider selection happens once during FastAPI startup:

```python
# backend/app/market/provider.py
from app.core.config import Settings
from app.market.massive import MassiveMarketDataProvider
from app.market.simulator import SimulatedMarketDataProvider


def create_market_provider(settings: Settings) -> MarketDataProvider:
    api_key = settings.massive_api_key.strip()
    if api_key:
        return MassiveMarketDataProvider(
            api_key=api_key,
            stale_after_seconds=settings.market_stale_after_seconds,
        )
    return SimulatedMarketDataProvider(seed=settings.market_simulator_seed)


def default_poll_interval_seconds(settings: Settings) -> float:
    if settings.market_poll_interval_seconds is not None:
        return settings.market_poll_interval_seconds
    if settings.massive_api_key.strip():
        return 15.0
    return 0.5
```

Rules:

- Empty `MASSIVE_API_KEY` means simulator.
- Non-empty `MASSIVE_API_KEY` means Massive.
- A bad Massive key should produce degraded health and stale or unavailable data, not simulator data.
- The Massive default poll interval is `15.0` seconds to stay free-tier friendly.
- The simulator default poll interval is `0.5` seconds for visible UI movement.

## Domain Models

Use immutable dataclasses for backend market domain values. Pydantic request and response models may wrap these at API boundaries, but provider internals should stay lightweight.

```python
# backend/app/market/models.py
from __future__ import annotations

from dataclasses import dataclass, replace
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
        return (self.price - baseline) / baseline * 100.0

    @property
    def direction(self) -> str:
        if self.previous_price is None or self.price == self.previous_price:
            return "flat"
        return "up" if self.price > self.previous_price else "down"

    def with_previous_price(self, previous_price: float | None) -> "PriceQuote":
        return replace(self, previous_price=previous_price)


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


@dataclass(frozen=True, slots=True)
class MarketProviderHealth:
    source: MarketSource
    ok: bool
    message: str | None = None
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
```

Validation expectations:

- Tickers are normalized before they enter providers: trim whitespace and uppercase.
- Core accepted ticker format is `^[A-Z]{1,5}$`.
- Missing quotes are represented by absence from `dict[str, PriceQuote]`, not by zero prices.
- A quote with `price <= 0` is invalid and must be dropped before cache update.

## Provider Protocol

All market data providers implement the same async contract.

```python
# backend/app/market/provider.py
from __future__ import annotations

from typing import Protocol

from app.market.models import DailyBar, MarketProviderHealth, PriceQuote


class MarketDataProvider(Protocol):
    async def get_prices(self, tickers: set[str]) -> dict[str, PriceQuote]:
        """Return latest normalized prices keyed by uppercase ticker."""

    async def get_previous_day_bars(self, tickers: set[str]) -> dict[str, DailyBar]:
        """Return previous trading-day OHLCV bars keyed by uppercase ticker."""

    def health(self) -> MarketProviderHealth:
        """Return current provider status without network I/O."""
```

Provider rules:

- Accept a set of uppercase symbols.
- Return only symbols with valid prices.
- Batch network calls when the upstream API supports it.
- Never update portfolio, watchlist, or trade state.
- Never know about SSE clients.

## Price Cache

The cache is the source of truth for current prices inside FastAPI. All trade fills, portfolio valuation, watchlist responses, and SSE events read from it.

```python
# backend/app/market/cache.py
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
            quote = self._quotes.get(ticker.upper())
            return self._mark_stale(quote) if quote else None

    async def update_many(self, quotes: dict[str, PriceQuote]) -> None:
        async with self._lock:
            for ticker, quote in quotes.items():
                symbol = ticker.upper()
                if quote.price <= 0:
                    continue
                previous = self._quotes.get(symbol)
                previous_price = previous.price if previous else quote.previous_price
                self._quotes[symbol] = quote.with_previous_price(previous_price)

    def _mark_stale(self, quote: PriceQuote) -> PriceQuote:
        now = datetime.now(timezone.utc)
        age = (now - quote.timestamp).total_seconds()
        if age <= self._stale_after_seconds and not quote.stale:
            return quote
        return replace(quote, stale=True)
```

Cache behavior:

- Preserve prior cached price when a new quote arrives so `direction` drives price flashes consistently.
- Keep position tickers even after they are removed from the watchlist.
- Mark stale by timestamp on read so stale status changes even if no provider update arrives.
- Do not make network calls.
- Do not synthesize prices.

## Market Service

The market service owns the background provider polling loop and tracked ticker universe.

```python
# backend/app/market/service.py
from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from app.market.cache import PriceCache
from app.market.models import MarketProviderHealth
from app.market.provider import MarketDataProvider


TickerLoader = Callable[[], Awaitable[set[str]]]


class MarketDataService:
    def __init__(
        self,
        provider: MarketDataProvider,
        cache: PriceCache,
        ticker_loader: TickerLoader,
        poll_interval_seconds: float,
    ) -> None:
        self.provider = provider
        self.cache = cache
        self.ticker_loader = ticker_loader
        self.poll_interval_seconds = poll_interval_seconds
        self._tickers: set[str] = set()
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        if self._task is None:
            await self.refresh_tracked_tickers()
            self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def refresh_tracked_tickers(self) -> None:
        self._tickers = {ticker.upper() for ticker in await self.ticker_loader()}

    async def add_tracked_ticker(self, ticker: str) -> None:
        self._tickers.add(ticker.upper())

    async def refresh_once(self) -> None:
        if not self._tickers:
            return
        quotes = await self.provider.get_prices(set(self._tickers))
        await self.cache.update_many(quotes)

    def health(self) -> MarketProviderHealth:
        return self.provider.health()

    async def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await self.refresh_tracked_tickers()
                await self.refresh_once()
            except Exception:
                # Log with app logger in implementation. Provider health should
                # carry expected upstream failures; this guard keeps the loop alive.
                pass
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.poll_interval_seconds)
            except TimeoutError:
                continue
```

The ticker loader should return the union of:

- Default or saved watchlist tickers.
- Tickers from open positions.
- Any ticker just traded or added by the LLM/manual watchlist API.

Example loader:

```python
async def load_tracked_tickers(db: Database) -> set[str]:
    watchlist = await db.fetch_watchlist_tickers(user_id="default")
    positions = await db.fetch_position_tickers(user_id="default")
    return set(watchlist) | set(positions)
```

## FastAPI Lifecycle Wiring

Create the provider, cache, and service during app startup. Store them in `app.state` for route dependencies.

```python
# backend/app/main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.market.cache import PriceCache
from app.market.provider import create_market_provider, default_poll_interval_seconds
from app.market.service import MarketDataService


@asynccontextmanager
async def lifespan(app: FastAPI):
    provider = create_market_provider(settings)
    cache = PriceCache(stale_after_seconds=settings.market_stale_after_seconds)
    service = MarketDataService(
        provider=provider,
        cache=cache,
        ticker_loader=lambda: load_tracked_tickers(app.state.db),
        poll_interval_seconds=default_poll_interval_seconds(settings),
    )
    app.state.market_cache = cache
    app.state.market_service = service
    await service.start()
    yield
    await service.stop()


app = FastAPI(lifespan=lifespan)
```

Dependency helper:

```python
from fastapi import Request


def get_market_service(request: Request) -> MarketDataService:
    return request.app.state.market_service
```

## Simulator Provider

The simulator is the default implementation. It updates requested tickers once per `get_prices()` call.

```python
# backend/app/market/simulator.py
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timezone
from math import exp

from app.market.models import (
    DailyBar,
    MarketProviderHealth,
    MarketSession,
    MarketSource,
    PriceQuote,
)


DEFAULT_SEED_PRICES = {
    "AAPL": 190.00,
    "MSFT": 430.00,
    "NVDA": 120.00,
    "GOOGL": 175.00,
    "AMZN": 185.00,
    "META": 500.00,
    "TSLA": 250.00,
    "NFLX": 650.00,
    "AMD": 160.00,
    "SPY": 550.00,
    "JPM": 210.00,
    "V": 275.00,
}


@dataclass(slots=True)
class SimulatedTickerState:
    ticker: str
    price: float
    previous_price: float
    previous_close: float
    day_open: float
    day_high: float
    day_low: float
    volume: float
    beta: float
    rng: random.Random
    updated_at: datetime


def seed_price_for_ticker(ticker: str) -> float:
    value = sum((index + 1) * ord(char) for index, char in enumerate(ticker))
    return round(25.0 + (value % 475), 2)


def ticker_seed(global_seed: int, ticker: str) -> int:
    return global_seed + sum((index + 1) * ord(char) for index, char in enumerate(ticker))


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class SimulatedMarketDataProvider:
    def __init__(self, seed: int = 42) -> None:
        self._seed = seed
        self._market_rng = random.Random(seed)
        self._states: dict[str, SimulatedTickerState] = {}

    async def get_prices(self, tickers: set[str]) -> dict[str, PriceQuote]:
        symbols = sorted({ticker.upper() for ticker in tickers})
        if not symbols:
            return {}

        trading_seconds_per_year = 252 * 6.5 * 60 * 60
        dt_years = 0.5 / trading_seconds_per_year
        market_sigma = 0.20 * 0.35 * (dt_years ** 0.5)
        market_move = self._market_rng.gauss(0.0, market_sigma)

        quotes: dict[str, PriceQuote] = {}
        for symbol in symbols:
            state = self._state_for(symbol)
            self._states[symbol] = self._next_state(state, market_move, dt_years)
            quotes[symbol] = self._quote_for(self._states[symbol])
        return quotes

    async def get_previous_day_bars(self, tickers: set[str]) -> dict[str, DailyBar]:
        bars: dict[str, DailyBar] = {}
        for symbol in sorted({ticker.upper() for ticker in tickers}):
            state = self._state_for(symbol)
            rng = random.Random(ticker_seed(self._seed, symbol) + 10_000)
            close = state.previous_close
            open_price = round(close * rng.uniform(0.98, 1.02), 2)
            high = round(max(open_price, close) * rng.uniform(1.00, 1.03), 2)
            low = round(min(open_price, close) * rng.uniform(0.97, 1.00), 2)
            volume = float(rng.randint(1_000_000, 80_000_000))
            bars[symbol] = DailyBar(
                ticker=symbol,
                date=datetime.now(timezone.utc).date().isoformat(),
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=volume,
                vwap=round((open_price + high + low + close) / 4, 2),
                source=MarketSource.SIMULATOR,
            )
        return bars

    def health(self) -> MarketProviderHealth:
        return MarketProviderHealth(
            source=MarketSource.SIMULATOR,
            ok=True,
            message="simulator running",
            last_success_at=datetime.now(timezone.utc),
        )

    def _state_for(self, ticker: str) -> SimulatedTickerState:
        existing = self._states.get(ticker)
        if existing:
            return existing

        rng = random.Random(ticker_seed(self._seed, ticker))
        price = DEFAULT_SEED_PRICES.get(ticker, seed_price_for_ticker(ticker))
        beta = rng.uniform(0.7, 1.3)
        now = datetime.now(timezone.utc)
        state = SimulatedTickerState(
            ticker=ticker,
            price=price,
            previous_price=price,
            previous_close=price,
            day_open=price,
            day_high=price,
            day_low=price,
            volume=0.0,
            beta=beta,
            rng=rng,
            updated_at=now,
        )
        self._states[ticker] = state
        return state

    def _next_state(
        self,
        state: SimulatedTickerState,
        market_move: float,
        dt_years: float,
    ) -> SimulatedTickerState:
        drift = 0.05 * dt_years
        sigma = 0.20 * (dt_years ** 0.5)
        idiosyncratic = state.rng.gauss(0.0, sigma)
        raw_return = drift + state.beta * market_move + idiosyncratic
        bounded_return = clamp(raw_return, -0.02, 0.02)
        new_price = round(max(0.01, state.price * exp(bounded_return)), 2)

        return SimulatedTickerState(
            ticker=state.ticker,
            price=new_price,
            previous_price=state.price,
            previous_close=state.previous_close,
            day_open=state.day_open,
            day_high=max(state.day_high, new_price),
            day_low=min(state.day_low, new_price),
            volume=state.volume + state.rng.randint(100, 10_000),
            beta=state.beta,
            rng=state.rng,
            updated_at=datetime.now(timezone.utc),
        )

    def _quote_for(self, state: SimulatedTickerState) -> PriceQuote:
        return PriceQuote(
            ticker=state.ticker,
            price=state.price,
            previous_price=state.previous_price,
            previous_close=state.previous_close,
            timestamp=state.updated_at,
            source=MarketSource.SIMULATOR,
            session=MarketSession.OPEN,
            stale=False,
            volume=state.volume,
            day_open=state.day_open,
            day_high=state.day_high,
            day_low=state.day_low,
        )
```

Simulator behavior for newly added tickers:

1. Normalize to uppercase.
2. Create deterministic state from `ticker_seed`.
3. Include it in the next `get_prices()` result.
4. The service updates the cache.
5. The SSE stream publishes it in the next batch.

## Massive Provider

Use direct `httpx` calls for the first implementation. The project only needs a few REST endpoints, and direct mapping keeps the adapter teachable.

Endpoint for latest multi-ticker prices:

```text
GET https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,MSFT,NVDA
```

Authentication:

```http
Authorization: Bearer $MASSIVE_API_KEY
```

Price selection order:

1. `lastTrade.p`
2. Midpoint of `lastQuote.p` bid and `lastQuote.P` ask
3. `min.c`
4. `day.c`
5. `prevDay.c` as stale fallback

Implementation:

```python
# backend/app/market/massive.py
from __future__ import annotations

import asyncio
import random
from dataclasses import replace
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.market.models import (
    DailyBar,
    MarketProviderHealth,
    MarketSession,
    MarketSource,
    PriceQuote,
)


BASE_URL = "https://api.massive.com"


def ns_to_datetime(value: int | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1_000_000_000, tz=timezone.utc)


def ms_to_datetime(value: int | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1_000, tz=timezone.utc)


def positive_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def choose_snapshot_price(snapshot: dict[str, Any]) -> tuple[float | None, datetime | None, bool]:
    last_trade = snapshot.get("lastTrade") or {}
    trade_price = positive_float(last_trade.get("p"))
    if trade_price:
        return trade_price, ns_to_datetime(last_trade.get("t")), False

    last_quote = snapshot.get("lastQuote") or {}
    bid = positive_float(last_quote.get("p"))
    ask = positive_float(last_quote.get("P"))
    if bid and ask:
        return round((bid + ask) / 2, 4), ns_to_datetime(last_quote.get("t")), False

    minute = snapshot.get("min") or {}
    minute_close = positive_float(minute.get("c"))
    if minute_close:
        return minute_close, ms_to_datetime(minute.get("t")), False

    day = snapshot.get("day") or {}
    day_close = positive_float(day.get("c"))
    if day_close:
        return day_close, None, False

    prev_day = snapshot.get("prevDay") or {}
    prev_close = positive_float(prev_day.get("c"))
    if prev_close:
        return prev_close, None, True

    return None, None, True


def retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())


class MassiveMarketDataProvider:
    def __init__(self, api_key: str, stale_after_seconds: float = 30.0) -> None:
        self._api_key = api_key
        self._stale_after_seconds = stale_after_seconds
        self._health = MarketProviderHealth(
            source=MarketSource.MASSIVE,
            ok=True,
            message="not yet polled",
        )
        self._backoff_until: datetime | None = None
        self._failures = 0

    async def get_prices(self, tickers: set[str]) -> dict[str, PriceQuote]:
        symbols = sorted({ticker.upper() for ticker in tickers})
        if not symbols:
            return {}
        if self._in_backoff():
            self._mark_unhealthy("provider backoff active")
            return {}

        try:
            snapshots = await self._fetch_snapshots(symbols)
        except httpx.HTTPStatusError as exc:
            self._handle_http_error(exc)
            return {}
        except (httpx.RequestError, TimeoutError) as exc:
            self._handle_transient_error(f"network error: {exc.__class__.__name__}")
            return {}

        now = datetime.now(timezone.utc)
        self._failures = 0
        self._health = MarketProviderHealth(
            source=MarketSource.MASSIVE,
            ok=True,
            message="ok",
            last_success_at=now,
        )

        quotes: dict[str, PriceQuote] = {}
        for snapshot in snapshots:
            quote = self._map_snapshot(snapshot, now)
            if quote:
                quotes[quote.ticker] = quote
        return quotes

    async def get_previous_day_bars(self, tickers: set[str]) -> dict[str, DailyBar]:
        bars: dict[str, DailyBar] = {}
        for ticker in sorted({ticker.upper() for ticker in tickers}):
            bar = await self._fetch_previous_day_bar(ticker)
            if bar:
                bars[ticker] = bar
        return bars

    def health(self) -> MarketProviderHealth:
        return self._health

    async def _fetch_snapshots(self, symbols: list[str]) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
            response = await client.get(
                "/v2/snapshot/locale/us/markets/stocks/tickers",
                params={"tickers": ",".join(symbols)},
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            response.raise_for_status()
            payload = response.json()
        return payload.get("tickers", [])

    async def _fetch_previous_day_bar(self, ticker: str) -> DailyBar | None:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
            response = await client.get(
                f"/v2/aggs/ticker/{ticker}/prev",
                params={"adjusted": "true"},
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            response.raise_for_status()
            payload = response.json()
        results = payload.get("results") or []
        if not results:
            return None
        result = results[0]
        timestamp = ms_to_datetime(result.get("t"))
        return DailyBar(
            ticker=ticker,
            date=timestamp.date().isoformat() if timestamp else datetime.now(timezone.utc).date().isoformat(),
            open=float(result["o"]),
            high=float(result["h"]),
            low=float(result["l"]),
            close=float(result["c"]),
            volume=float(result["v"]) if result.get("v") is not None else None,
            vwap=float(result["vw"]) if result.get("vw") is not None else None,
            source=MarketSource.MASSIVE,
            adjusted=True,
        )

    def _map_snapshot(self, snapshot: dict[str, Any], now: datetime) -> PriceQuote | None:
        ticker = str(snapshot.get("ticker") or "").upper()
        if not ticker:
            return None

        price, timestamp, stale_from_fallback = choose_snapshot_price(snapshot)
        if price is None:
            return None

        prev_day = snapshot.get("prevDay") or {}
        day = snapshot.get("day") or {}
        selected_timestamp = timestamp or ns_to_datetime(snapshot.get("updated")) or now
        age = (now - selected_timestamp).total_seconds()
        stale = stale_from_fallback or age > self._stale_after_seconds

        return PriceQuote(
            ticker=ticker,
            price=price,
            previous_price=None,
            previous_close=positive_float(prev_day.get("c")),
            timestamp=selected_timestamp,
            source=MarketSource.MASSIVE,
            session=MarketSession.UNKNOWN,
            stale=stale,
            volume=positive_float(day.get("v")),
            day_open=positive_float(day.get("o")),
            day_high=positive_float(day.get("h")),
            day_low=positive_float(day.get("l")),
        )

    def _handle_http_error(self, exc: httpx.HTTPStatusError) -> None:
        status = exc.response.status_code
        if status in (401, 403):
            self._backoff_until = None
            self._mark_unhealthy("Massive API authentication failed")
            return
        if status == 429:
            retry_after = retry_after_seconds(exc.response.headers.get("Retry-After"))
            self._schedule_backoff(retry_after)
            self._mark_unhealthy("Massive API rate limited")
            return
        if status >= 500:
            self._schedule_backoff()
            self._mark_unhealthy(f"Massive API server error {status}")
            return
        self._mark_unhealthy(f"Massive API error {status}")

    def _handle_transient_error(self, message: str) -> None:
        self._schedule_backoff()
        self._mark_unhealthy(message)

    def _schedule_backoff(self, retry_after: float | None = None) -> None:
        self._failures += 1
        delay = retry_after if retry_after is not None else min(60.0, 2 ** self._failures)
        delay += random.uniform(0.0, min(1.0, delay * 0.1))
        self._backoff_until = datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() + delay, tz=timezone.utc)

    def _in_backoff(self) -> bool:
        return self._backoff_until is not None and datetime.now(timezone.utc) < self._backoff_until

    def _mark_unhealthy(self, message: str) -> None:
        self._health = replace(
            self._health,
            ok=False,
            message=message,
            last_error_at=datetime.now(timezone.utc),
        )
```

Massive behavior:

- `401` or `403`: mark unhealthy with a configuration/auth message.
- `429`: honor `Retry-After` when available; otherwise use exponential backoff with jitter.
- `5xx` and network failures: degraded health and bounded backoff.
- Missing ticker in response: return no quote for that ticker; the cache keeps old data if available.
- Closed market or delayed data: keep `source="massive"` and mark stale when appropriate.

## API Serialization

Use one serializer for REST and SSE payloads so the UI sees identical quote fields everywhere.

```python
# backend/app/market/serialization.py
from app.market.models import PriceQuote


def quote_to_payload(quote: PriceQuote) -> dict:
    return {
        "ticker": quote.ticker,
        "price": quote.price,
        "previous_price": quote.previous_price,
        "previous_close": quote.previous_close,
        "change": quote.change,
        "change_percent": quote.change_percent,
        "direction": quote.direction,
        "timestamp": quote.timestamp.isoformat().replace("+00:00", "Z"),
        "stale": quote.stale,
        "source": quote.source.value,
        "session": quote.session.value,
        "volume": quote.volume,
        "day_open": quote.day_open,
        "day_high": quote.day_high,
        "day_low": quote.day_low,
    }
```

SSE batch payload:

```json
{
  "type": "prices",
  "timestamp": "2026-07-30T12:00:00Z",
  "prices": [
    {
      "ticker": "AAPL",
      "price": 190.12,
      "previous_price": 189.88,
      "previous_close": 190.0,
      "change": 0.12,
      "change_percent": 0.0631578947,
      "direction": "up",
      "timestamp": "2026-07-30T12:00:00Z",
      "stale": false,
      "source": "simulator",
      "session": "open",
      "volume": 52814.0,
      "day_open": 190.0,
      "day_high": 190.12,
      "day_low": 189.88
    }
  ]
}
```

Heartbeat payload:

```json
{
  "type": "heartbeat",
  "timestamp": "2026-07-30T12:00:00Z"
}
```

## SSE Streaming

The SSE route publishes from cache. It never calls providers directly.

```python
# backend/app/api/stream.py
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from app.market.serialization import quote_to_payload
from app.market.service import MarketDataService


router = APIRouter(prefix="/api/stream", tags=["stream"])


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@router.get("/prices")
async def stream_prices(request: Request) -> EventSourceResponse:
    service: MarketDataService = request.app.state.market_service

    async def events():
        last_payload = ""
        while True:
            if await request.is_disconnected():
                break

            snapshot = await service.cache.snapshot()
            payload = {
                "type": "prices",
                "timestamp": utc_now(),
                "prices": [quote_to_payload(quote) for quote in snapshot.values()],
            }
            encoded = json.dumps(payload, separators=(",", ":"))

            if encoded != last_payload:
                last_payload = encoded
                yield {"event": "prices", "data": encoded}
            else:
                yield {"event": "heartbeat", "data": json.dumps({"type": "heartbeat", "timestamp": utc_now()})}

            await asyncio.sleep(0.5)

    return EventSourceResponse(events(), ping=15)
```

SSE behavior:

- Send an initial snapshot immediately.
- Publish cache snapshots every `0.5` seconds.
- In simulator mode, cache normally changes at the same cadence.
- In Massive mode, cache changes on the slower REST poll interval; heartbeats still prove the connection is alive.
- The frontend uses native `EventSource` reconnection.

## REST Endpoints

Market data REST endpoints are optional but useful for debugging and frontend initial hydration.

```python
# backend/app/api/market.py
from fastapi import APIRouter, HTTPException, Request

from app.market.serialization import quote_to_payload
from app.market.service import MarketDataService


router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/prices")
async def get_prices(request: Request) -> dict:
    service: MarketDataService = request.app.state.market_service
    snapshot = await service.cache.snapshot()
    return {"prices": [quote_to_payload(quote) for quote in snapshot.values()]}


@router.get("/prices/{ticker}")
async def get_price(ticker: str, request: Request) -> dict:
    service: MarketDataService = request.app.state.market_service
    quote = await service.cache.get(ticker)
    if quote is None:
        raise HTTPException(status_code=404, detail={"code": "PRICE_UNAVAILABLE", "ticker": ticker.upper()})
    return {"price": quote_to_payload(quote)}


@router.get("/health")
async def market_health(request: Request) -> dict:
    service: MarketDataService = request.app.state.market_service
    health = service.health()
    return {
        "source": health.source.value,
        "ok": health.ok,
        "message": health.message,
        "last_success_at": health.last_success_at.isoformat().replace("+00:00", "Z") if health.last_success_at else None,
        "last_error_at": health.last_error_at.isoformat().replace("+00:00", "Z") if health.last_error_at else None,
    }
```

Portfolio and watchlist endpoints should use the same service/cache:

```python
quote = await market_service.cache.get(ticker)
if quote is None:
    return error("PRICE_UNAVAILABLE", f"No current price for {ticker}.")
fill_price = quote.price
```

## Watchlist Integration

Manual and LLM watchlist changes must update both SQLite and the service ticker universe.

Add ticker flow:

1. Normalize and validate ticker.
2. Insert into `watchlist` with `UNIQUE(user_id, ticker)`.
3. Call `market_service.add_tracked_ticker(ticker)`.
4. Call `market_service.refresh_once()` to make the first price available quickly.
5. Return the latest quote if available.

Example:

```python
async def add_watchlist_ticker(ticker: str, db: Database, market: MarketDataService) -> dict:
    symbol = normalize_ticker(ticker)
    validate_ticker(symbol)
    await db.insert_watchlist_ticker(user_id="default", ticker=symbol)
    await market.add_tracked_ticker(symbol)
    await market.refresh_once()
    quote = await market.cache.get(symbol)
    return {"ticker": symbol, "price": quote_to_payload(quote) if quote else None}
```

Remove ticker flow:

1. Delete from `watchlist`.
2. Do not remove directly from cache.
3. Let the next `refresh_tracked_tickers()` compute watchlist union positions.
4. If the ticker is still held in positions, keep tracking it.

## Trade Integration

Market orders fill at the cache price currently shown to the user. The trade service must not call Massive or the simulator directly.

Buy flow:

```python
async def execute_buy(ticker: str, quantity: float, db: Database, market: MarketDataService) -> dict:
    symbol = normalize_ticker(ticker)
    validate_ticker(symbol)
    validate_quantity(quantity)

    quote = await market.cache.get(symbol)
    if quote is None:
        await market.add_tracked_ticker(symbol)
        await market.refresh_once()
        quote = await market.cache.get(symbol)
    if quote is None:
        return error("PRICE_UNAVAILABLE", f"No current price for {symbol}.")

    notional = round(quantity * quote.price, 2)
    profile = await db.fetch_user_profile("default")
    if profile.cash_balance < notional:
        return error("INSUFFICIENT_CASH", f"Not enough cash to buy {quantity} shares of {symbol}.")

    # In the real implementation, perform these DB writes in one transaction.
    trade = await db.insert_trade("default", symbol, "buy", quantity, quote.price)
    position = await db.upsert_buy_position("default", symbol, quantity, quote.price)
    await db.update_cash_balance("default", profile.cash_balance - notional)
    await db.insert_watchlist_ticker_if_missing("default", symbol)
    await market.add_tracked_ticker(symbol)
    await record_portfolio_snapshot(db, market)
    return {"trade": trade, "position": position, "fill_price": quote.price}
```

Sell flow:

- Validate ticker and quantity.
- Read fill price from cache.
- Confirm held quantity is sufficient.
- Update or delete the position.
- Increase cash.
- Insert trade.
- Record portfolio snapshot.
- Keep ticker in watchlist if already present; do not force-remove after selling.

## Portfolio Valuation

Portfolio values should read one cache snapshot and use it consistently for the response.

```python
async def build_portfolio_response(db: Database, market: MarketDataService) -> dict:
    profile = await db.fetch_user_profile("default")
    positions = await db.fetch_positions("default")
    prices = await market.cache.snapshot()

    position_rows = []
    market_value = 0.0
    for position in positions:
        quote = prices.get(position.ticker)
        current_price = quote.price if quote else None
        value = position.quantity * current_price if current_price is not None else 0.0
        cost_basis = position.quantity * position.avg_cost
        unrealized_pnl = value - cost_basis if current_price is not None else None
        market_value += value
        position_rows.append({
            "ticker": position.ticker,
            "quantity": position.quantity,
            "avg_cost": position.avg_cost,
            "current_price": current_price,
            "market_value": value,
            "unrealized_pnl": unrealized_pnl,
            "unrealized_return_percent": (unrealized_pnl / cost_basis * 100.0) if unrealized_pnl is not None and cost_basis else None,
            "stale": quote.stale if quote else True,
        })

    return {
        "cash_balance": profile.cash_balance,
        "positions": position_rows,
        "total_value": profile.cash_balance + market_value,
    }
```

## LLM Context

The chat service should include market data from the cache, not provider-specific calls.

Example context:

```json
{
  "market_data_source": "simulator",
  "watchlist": [
    {"ticker": "AAPL", "price": 190.12, "change_percent": 0.06, "stale": false}
  ],
  "positions": [
    {"ticker": "AAPL", "quantity": 2.5, "avg_cost": 188.0, "current_price": 190.12}
  ]
}
```

If `source="massive"` and `stale=true`, the assistant prompt should state that prices may be delayed or closed-market values. Do not hide staleness from the LLM.

## Error Shape

Market-related errors should follow the project-wide shape:

```json
{
  "error": {
    "code": "PRICE_UNAVAILABLE",
    "message": "No current price is available for AAPL.",
    "details": {
      "ticker": "AAPL",
      "source": "massive"
    }
  }
}
```

Recommended market error codes:

| Code | Use |
|---|---|
| `INVALID_TICKER` | Ticker format is not supported |
| `PRICE_UNAVAILABLE` | No valid current or cached price exists |
| `MARKET_PROVIDER_UNHEALTHY` | Massive auth, rate-limit, or network issue affects data |
| `MARKET_DATA_STALE` | Operation requires fresh prices but only stale data exists |
| `MASSIVE_AUTH_FAILED` | Massive returned 401 or 403 |
| `MASSIVE_RATE_LIMITED` | Massive returned 429 |

For simulator mode, stale data should rarely occur. For Massive mode, stale prices are acceptable for UI display but can be rejected for trade fills if product requirements later require fresh execution prices. Initial implementation may allow fills from stale Massive data if the response clearly marks the fill source and `stale=true`.

## Test Plan

Unit tests:

- `create_market_provider()` returns simulator without `MASSIVE_API_KEY`.
- `create_market_provider()` returns Massive with a non-empty `MASSIVE_API_KEY`.
- Simulator emits deterministic prices for the same seed and ticker sequence.
- Simulator unknown ticker seed price is stable.
- Simulator prices stay positive.
- Simulator per-tick moves are bounded.
- Simulator `previous_price` equals the prior emitted `price`.
- Simulator daily bars satisfy `low <= open <= high` and `low <= close <= high`.
- Massive parser uses fallback order: trade, quote midpoint, minute close, day close, previous close.
- Massive parser converts nanosecond and millisecond timestamps to UTC datetimes.
- Massive parser drops invalid zero or missing prices.
- Massive `401` and `403` update health without simulator fallback.
- Massive `429` schedules backoff and returns no new quotes.
- Cache preserves previous cached price across updates.
- Cache marks old quotes stale on read.
- Market service uses watchlist union positions.

Integration tests:

- With no `MASSIVE_API_KEY`, `/api/stream/prices` emits simulator prices within one second.
- Adding a watchlist ticker includes it in the next SSE price batch.
- Removing a watchlist ticker does not stop tracking if it is still held.
- Market order fills from cache and does not call the provider directly.
- Portfolio response uses one cache snapshot consistently.
- Massive fixture response updates cache and SSE payloads with `source="massive"`.
- Massive provider failure leaves old cached values available with stale flags.

E2E tests:

- Fresh start shows default watchlist and streaming prices.
- Buy order changes cash, position table, portfolio total, and snapshots.
- Sell order changes cash, positions, portfolio total, and snapshots.
- SSE reconnect resumes updates.
- `LLM_MOCK=true` chat can execute a mock trade using the same cache fill path.

## Implementation Sequence

1. Add settings, market models, provider protocol, and serializer.
2. Implement `PriceCache`.
3. Implement `SimulatedMarketDataProvider` and its unit tests.
4. Implement `MarketDataService` and FastAPI lifespan wiring.
5. Add `/api/stream/prices` and optional `/api/market/*` diagnostics.
6. Wire watchlist, trade execution, portfolio valuation, and LLM context to cache reads.
7. Implement `MassiveMarketDataProvider` with fixture-based parser tests.
8. Add Massive health, rate-limit, and stale-data integration tests.

## Guardrails

- The SSE layer reads from cache only.
- Trade execution reads from cache only.
- Provider code never writes to SQLite.
- Portfolio code never calls providers directly.
- Simulator code never imports Massive code.
- Massive failures never trigger an in-process simulator fallback.
- Prices with `price <= 0` are invalid.
- API payloads are JSON objects, not bare arrays.
- Every timestamp crossing the API boundary is UTC ISO 8601.
