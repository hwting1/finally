# Market Data Backend Summary

Updated: 2026-07-30

This is the live summary for FinAlly's market data backend. Earlier design, research, simulator, interface, and review notes are preserved in `planning/archive/`.

## Current Status

The market data backend foundation is implemented and tested. It provides:

- A provider-independent market domain model.
- A deterministic simulator for default no-key operation.
- A Massive REST provider for real market data when `MASSIVE_API_KEY` is configured.
- A shared in-memory price cache used by API and stream endpoints.
- A market service that owns ticker tracking and background refresh.
- REST diagnostics for current prices and provider health.
- Server-Sent Events for live price streaming.
- A Rich terminal simulator demo.

The backend is ready for portfolio, watchlist, frontend, and LLM agents to consume current prices from the cache and SSE stream instead of calling providers directly.

## Implemented Files

Backend application:

- `backend/app/main.py` creates the FastAPI app, wires market service startup/shutdown, and exposes `/api/health`.
- `backend/app/core/config.py` centralizes market settings from `.env` and `../.env`.
- `backend/app/api/market.py` exposes cache-backed market diagnostics:
  - `GET /api/market/prices`
  - `GET /api/market/prices/{ticker}`
  - `GET /api/market/health`
- `backend/app/api/stream.py` exposes `GET /api/stream/prices` as a Server-Sent Events stream.

Market package:

- `backend/app/market/models.py` defines `PriceQuote`, `DailyBar`, `MarketProviderHealth`, `MarketSource`, and `MarketSession`.
- `backend/app/market/provider.py` defines the provider protocol, provider factory, and default poll interval rules.
- `backend/app/market/simulator.py` implements deterministic GBM-style simulated prices.
- `backend/app/market/massive.py` implements Massive REST snapshot and previous-day-bar parsing.
- `backend/app/market/cache.py` implements the shared latest-price cache and stale marking.
- `backend/app/market/service.py` owns tracked tickers and background refresh.
- `backend/app/market/serialization.py` converts quotes and health objects into API/SSE payloads.
- `backend/app/market/validation.py` centralizes ticker normalization and `^[A-Z]{1,5}$` validation.

Demo:

- `backend/market_data_demo.py` runs a 60-second Rich terminal dashboard for all 10 default simulator tickers, with live prices, sparklines, direction arrows, notable-move log, and seed-vs-final summary.

Tests:

- `backend/tests/test_simulator.py`
- `backend/tests/test_cache_service_provider.py`
- `backend/tests/test_massive.py`
- `backend/tests/test_api.py`

Dependency metadata:

- `backend/pyproject.toml`
- `backend/uv.lock`

## Provider Behavior

Provider selection happens once at FastAPI startup:

- Empty `MASSIVE_API_KEY` selects `SimulatedMarketDataProvider`.
- Non-empty `MASSIVE_API_KEY` selects `MassiveMarketDataProvider`.
- The backend does not fall back from Massive to simulated prices after startup. Massive authentication, rate-limit, server, and network failures mark provider health degraded and return no new quotes, leaving old cache values available for consumers.

Default poll intervals:

- Simulator: `0.5` seconds.
- Massive: `15.0` seconds, unless `MARKET_POLL_INTERVAL_SECONDS` is set.

Relevant settings:

- `MASSIVE_API_KEY`
- `MARKET_POLL_INTERVAL_SECONDS`
- `MARKET_STALE_AFTER_SECONDS`
- `MARKET_SIMULATOR_SEED`

## Simulator Details

The simulator:

- Uses deterministic random generators, not global randomness.
- Updates prices on each `get_prices()` call.
- Uses a weak shared market factor plus per-ticker idiosyncratic movement.
- Floors prices above zero.
- Clamps per-tick returns to avoid extreme jumps.
- Emits `source="simulator"`, `session="open"`, and `stale=false`.
- Produces deterministic previous-day OHLCV bars with valid low/open/high/close relationships.

The explicit default seed tickers now match the planned first-launch watchlist:

- `AAPL`
- `GOOGL`
- `MSFT`
- `AMZN`
- `TSLA`
- `NVDA`
- `META`
- `JPM`
- `V`
- `NFLX`

Unknown but valid tickers still receive deterministic fallback seed prices.

## Massive REST Details

The Massive provider:

- Uses `https://api.massive.com`.
- Sends credentials in the `Authorization: Bearer` header.
- Uses the multi-ticker snapshot endpoint:
  - `/v2/snapshot/locale/us/markets/stocks/tickers`
- Supports previous-day bars:
  - `/v2/aggs/ticker/{ticker}/prev`

Snapshot price fallback order:

1. `lastTrade.p`
2. Bid/ask midpoint from `lastQuote.p` and `lastQuote.P`
3. `min.c`
4. `day.c`
5. `prevDay.c` as a stale fallback

Timestamp handling:

- Nanosecond timestamps are converted with `ns_to_datetime()`.
- Millisecond timestamps are converted with `ms_to_datetime()`.
- API payloads serialize UTC timestamps with a `Z` suffix.

Health handling:

- `401` / `403`: unhealthy, `Massive API authentication failed`.
- `429`: unhealthy, `Massive API rate limited`.
- `5xx`: unhealthy with server-error status.
- Network errors: unhealthy with network-error message.

## Cache And Service

`PriceCache` is the source of truth for current prices inside the backend.

It:

- Stores latest quotes by uppercase ticker.
- Preserves the previous cached price when a ticker updates so `direction` is stable for UI flashes.
- Drops invalid zero or negative prices.
- Marks quotes stale on read when their timestamps age past the configured threshold.

`MarketDataService`:

- Loads the default tracked ticker set.
- Preserves tickers added at runtime.
- Filters invalid symbols before provider calls.
- Refreshes provider data into the cache.
- Runs a background loop under FastAPI lifespan.
- Exposes provider health without network I/O.

## API Contracts

Current market REST responses return JSON objects rather than bare arrays.

`GET /api/market/prices`:

```json
{
  "prices": [
    {
      "ticker": "AAPL",
      "price": 190.12,
      "previous_price": 189.88,
      "previous_close": 190.0,
      "change": 0.12,
      "change_percent": 0.0631,
      "direction": "up",
      "timestamp": "2026-07-30T12:00:00Z",
      "stale": false,
      "source": "simulator",
      "session": "open"
    }
  ]
}
```

`GET /api/market/prices/{ticker}`:

- Validates ticker as `^[A-Z]{1,5}$` after trimming and uppercasing.
- Adds a valid missing ticker to tracking.
- Refreshes once so a price is available quickly.
- Returns `400` for invalid tickers and `404` if market data remains unavailable.

`GET /api/market/health`:

```json
{
  "market": {
    "source": "simulator",
    "ok": true,
    "message": null,
    "last_success_at": "2026-07-30T12:00:00Z",
    "last_error_at": null
  }
}
```

`GET /api/stream/prices`:

- Streams Server-Sent Events.
- Emits `prices` events when cache has quotes.
- Emits `heartbeat` events if no quotes are available.
- Reads from cache only; it does not call providers directly.

## Terminal Demo

Run:

```bash
cd backend
uv run python market_data_demo.py
```

Behavior:

- Runs for 60 seconds or until Ctrl+C.
- Displays all 10 default tickers.
- Shows live GBM-simulated prices.
- Shows direction arrows and color-coded price movement.
- Shows sparklines built from session history.
- Logs notable tick, session, new-high, and new-low events.
- Prints a session summary comparing final prices to seed prices.

## Tests Run

Primary validation command:

```bash
cd backend && uv run pytest
```

Latest result:

```text
24 passed
```

Additional validation:

```bash
cd backend && uv run python -m compileall app tests market_data_demo.py
```

Result: passed.

Import check for the demo:

```bash
cd backend && uv run python -c "import market_data_demo; print(len(market_data_demo.TICKERS), market_data_demo.RUN_SECONDS)"
```

Result:

```text
10 60.0
```

## Review Findings Addressed

Addressed:

- Added FastAPI application wiring.
- Added market cache.
- Added market service loop.
- Added provider factory and poll interval logic.
- Added centralized settings.
- Added SSE stream route.
- Added REST diagnostics.
- Added Massive REST adapter.
- Added serialization helpers.
- Added ticker validation.
- Aligned simulator seed prices with the planned watchlist.
- Expanded tests from simulator-only coverage to provider/cache/service/API/Massive coverage.

Deliberate behavior:

- Initial simulator `previous_close` remains a deterministic value near the seed rather than exactly the seed. This makes first-screen daily change values more realistic while staying repeatable.

## Remaining Integration Work

The market data backend is ready for downstream consumers, but the broader product still needs:

- Portfolio trade execution to fill from `MarketDataService.cache`.
- Watchlist CRUD to update tracked tickers through `MarketDataService.add_tracked_ticker()`.
- LLM context builders to read market data from the cache and include stale/source fields.
- Frontend `EventSource` integration with `/api/stream/prices`.
- Static frontend serving and full-container launch scripts from the broader project plan.

Archived source notes:

- `planning/archive/MARKET_DATA_DESIGN.md`
- `planning/archive/MARKET_INTERFACE.md`
- `planning/archive/MARKET_SIMULATOR.md`
- `planning/archive/MASSIVE_API.md`
- `planning/archive/MARKET_DATA_REVIEW.md`
