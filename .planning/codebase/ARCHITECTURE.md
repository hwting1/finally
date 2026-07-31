<!-- refreshed: 2026-07-31 -->
# Architecture

**Analysis Date:** 2026-07-31

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                      │
│                     `backend/app/main.py`                    │
├──────────────────────────────┬──────────────────────────────┤
│ REST Market Diagnostics       │ SSE Price Stream             │
│ `backend/app/api/market.py`   │ `backend/app/api/stream.py`  │
└───────────────┬──────────────┴──────────────┬───────────────┘
                │                             │
                ▼                             ▼
┌─────────────────────────────────────────────────────────────┐
│                 Market Data Service Layer                    │
│                 `backend/app/market/service.py`              │
│                 `backend/app/market/cache.py`                │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 Provider Interface + Implementations         │
│ `backend/app/market/provider.py`                             │
│ `backend/app/market/simulator.py` / `backend/app/market/massive.py` │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│       In-Memory Quotes / Optional External Massive REST       │
│       `backend/app/market/cache.py` / `https://api.massive.com` │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| FastAPI app factory | Creates the app, wires routers, creates lifespan-managed market provider, cache, and service, and exposes `/api/health`. | `backend/app/main.py` |
| Market REST router | Serves cache-backed price snapshots, single-ticker lookup, ticker validation, on-demand ticker tracking, and market provider health. | `backend/app/api/market.py` |
| SSE stream router | Emits `prices` or `heartbeat` Server-Sent Events from the shared cache on the service polling cadence. | `backend/app/api/stream.py` |
| Runtime settings | Loads market runtime settings from `.env` and `../.env` via Pydantic settings without route-level config parsing. | `backend/app/core/config.py` |
| Market service | Owns tracked ticker state, merges the default watchlist with on-demand tickers, refreshes providers, and writes the cache. | `backend/app/market/service.py` |
| Price cache | Provides the process-local source of truth for latest normalized quotes, previous-price preservation, stale marking, and async lock protection. | `backend/app/market/cache.py` |
| Provider protocol and factory | Defines the provider contract and selects simulator or Massive from settings. | `backend/app/market/provider.py` |
| Simulator provider | Generates deterministic in-memory quotes and previous-day bars without network access. | `backend/app/market/simulator.py` |
| Massive provider | Calls Massive REST endpoints, maps snapshot/aggregate payloads into provider-independent models, and tracks provider health. | `backend/app/market/massive.py` |
| Domain models | Defines immutable provider-independent `PriceQuote`, `DailyBar`, `MarketProviderHealth`, `MarketSource`, and `MarketSession` values. | `backend/app/market/models.py` |
| Serialization helpers | Converts domain models to REST/SSE JSON payloads with UTC ISO timestamps. | `backend/app/market/serialization.py` |
| Validation helpers | Normalizes and validates ticker symbols with the shared `^[A-Z]{1,5}$` rule. | `backend/app/market/validation.py` |
| Terminal demo | Runs a Rich-based simulator dashboard directly against `SimulatedMarketDataProvider`. | `backend/market_data_demo.py` |

## Pattern Overview

**Overall:** Layered FastAPI service with protocol-based market data providers and a process-local cache.

**Key Characteristics:**
- HTTP routes in `backend/app/api/` adapt requests to service/cache calls and do not construct providers directly.
- `MarketDataService` in `backend/app/market/service.py` is the boundary for background polling, tracked ticker management, and cache writes.
- Provider-independent dataclasses in `backend/app/market/models.py` isolate the API and SSE layers from simulator and Massive response shapes.
- Runtime composition happens in the FastAPI lifespan in `backend/app/main.py`, not at import time inside route modules.
- The `PriceCache` in `backend/app/market/cache.py` is process-local and protected by `asyncio.Lock`.

## Layers

**Application Composition:**
- Purpose: Build the FastAPI app and manage process-lifetime market data objects.
- Location: `backend/app/main.py`
- Contains: `create_app()`, FastAPI lifespan, router registration, health endpoint, module-level `app`.
- Depends on: `backend/app/core/config.py`, `backend/app/api/market.py`, `backend/app/api/stream.py`, `backend/app/market/provider.py`, `backend/app/market/cache.py`, `backend/app/market/service.py`.
- Used by: Uvicorn command `uv run uvicorn app.main:app --reload` and tests in `backend/tests/test_api.py`.

**API Adapters:**
- Purpose: Convert HTTP requests and SSE connections into service/cache reads.
- Location: `backend/app/api/`
- Contains: `backend/app/api/market.py`, `backend/app/api/stream.py`, `backend/app/api/__init__.py`.
- Depends on: `backend/app/market/service.py`, `backend/app/market/serialization.py`, `backend/app/market/validation.py`.
- Used by: FastAPI router registration in `backend/app/main.py`.

**Configuration:**
- Purpose: Centralize environment-backed market settings.
- Location: `backend/app/core/`
- Contains: `backend/app/core/config.py`, `backend/app/core/__init__.py`.
- Depends on: `pydantic-settings` from `backend/pyproject.toml`.
- Used by: `backend/app/main.py` and test-specific app construction in `backend/tests/test_api.py`.

**Market Domain and Service:**
- Purpose: Represent provider-independent market values, cache latest prices, track tickers, and run refresh loops.
- Location: `backend/app/market/`
- Contains: `backend/app/market/models.py`, `backend/app/market/cache.py`, `backend/app/market/service.py`, `backend/app/market/serialization.py`, `backend/app/market/validation.py`.
- Depends on: Python standard library async/dataclass modules and the provider protocol in `backend/app/market/provider.py`.
- Used by: API routes in `backend/app/api/`, provider implementations in `backend/app/market/`, and `backend/market_data_demo.py`.

**Market Providers:**
- Purpose: Implement the same async quote/bar/health contract for simulator and Massive REST data.
- Location: `backend/app/market/`
- Contains: `backend/app/market/provider.py`, `backend/app/market/simulator.py`, `backend/app/market/massive.py`.
- Depends on: Domain models in `backend/app/market/models.py`, ticker helpers in `backend/app/market/validation.py`, and `httpx` for Massive.
- Used by: `create_market_provider()` in `backend/app/market/provider.py` and `MarketDataService` in `backend/app/market/service.py`.

**Demo Surface:**
- Purpose: Show simulator behavior in a terminal UI without starting FastAPI.
- Location: `backend/market_data_demo.py`
- Contains: Rich table/panel rendering, sparkline generation, event detection, and direct simulator polling.
- Depends on: `backend/app/market/simulator.py`, `backend/app/market/models.py`, `backend/app/market/service.py`.
- Used by: `uv run python market_data_demo.py`.

**Tests:**
- Purpose: Validate app routes, cache/service/provider factory behavior, simulator determinism, and Massive response handling.
- Location: `backend/tests/`
- Contains: `backend/tests/test_api.py`, `backend/tests/test_cache_service_provider.py`, `backend/tests/test_simulator.py`, `backend/tests/test_massive.py`.
- Depends on: `pytest`, `fastapi.testclient`, `httpx.MockTransport`, and app modules under `backend/app/`.
- Used by: `uv run pytest` from `backend/`.

## Data Flow

### Startup and Background Refresh Path

1. Uvicorn imports module-level `app = create_app()` (`backend/app/main.py:46`).
2. FastAPI lifespan creates a provider with `create_market_provider(app_settings)` (`backend/app/main.py:19`, `backend/app/market/provider.py:31`).
3. Lifespan creates `PriceCache` and `MarketDataService`, stores them on `app.state.market_cache` and `app.state.market_service` (`backend/app/main.py:20`, `backend/app/main.py:27`).
4. `MarketDataService.start()` loads default tracked tickers, refreshes once, and creates the async background task (`backend/app/market/service.py:55`).
5. `_run_loop()` repeatedly refreshes tracked tickers, calls the provider, and updates the cache (`backend/app/market/service.py:98`).
6. `PriceCache.update_many()` preserves previous prices, filters non-positive quotes, and stores normalized symbols (`backend/app/market/cache.py:27`).

### REST Price Snapshot Path

1. `GET /api/market/prices` enters `get_prices()` (`backend/app/api/market.py:19`).
2. The router reads `request.app.state.market_service` through `get_market_service()` (`backend/app/api/market.py:15`).
3. The route reads `service.cache.snapshot()` (`backend/app/api/market.py:22`, `backend/app/market/cache.py:18`).
4. Each `PriceQuote` is converted by `quote_to_payload()` (`backend/app/market/serialization.py:20`).
5. The route returns a JSON object with a `prices` array (`backend/app/api/market.py:23`).

### Single-Ticker Lookup Path

1. `GET /api/market/prices/{ticker}` normalizes and validates the ticker (`backend/app/api/market.py:26`, `backend/app/market/validation.py:11`).
2. Invalid symbols raise `HTTPException(status_code=400)` with `INVALID_TICKER` (`backend/app/api/market.py:29`).
3. The route checks `PriceCache.get()` for an existing quote (`backend/app/api/market.py:32`, `backend/app/market/cache.py:22`).
4. Missing valid symbols are added to the extra tracked set and refreshed once (`backend/app/api/market.py:33`, `backend/app/market/service.py:75`, `backend/app/market/service.py:87`).
5. If the provider still yields no quote, the route raises `HTTPException(status_code=404)` with `MARKET_DATA_UNAVAILABLE` (`backend/app/api/market.py:37`).
6. Available quotes return as a JSON object with a `price` payload (`backend/app/api/market.py:39`).

### SSE Price Stream Path

1. `GET /api/stream/prices` enters `stream_prices()` (`backend/app/api/stream.py:19`).
2. The route captures `request.app.state.market_service` (`backend/app/api/stream.py:21`).
3. The nested async generator loops until `request.is_disconnected()` (`backend/app/api/stream.py:23`).
4. Non-empty cache snapshots emit `event: prices` with serialized quote payloads (`backend/app/api/stream.py:25`).
5. Empty snapshots emit `event: heartbeat` (`backend/app/api/stream.py:33`).
6. The generator sleeps for `service.poll_interval_seconds` between events (`backend/app/api/stream.py:39`).

### Provider Selection Path

1. Settings load environment-backed values in `Settings` (`backend/app/core/config.py:8`).
2. `create_market_provider()` strips `massive_api_key` (`backend/app/market/provider.py:31`).
3. Non-empty `massive_api_key` returns `MassiveMarketDataProvider` (`backend/app/market/provider.py:33`).
4. Empty `massive_api_key` returns `SimulatedMarketDataProvider` seeded from settings (`backend/app/market/provider.py:41`).
5. Default poll interval is `15.0` seconds for Massive and `0.5` seconds for simulator unless overridden (`backend/app/market/provider.py:46`).

**State Management:**
- Process-level service and cache objects live on FastAPI `app.state` in `backend/app/main.py`.
- Latest prices live only in `PriceCache._quotes` in `backend/app/market/cache.py`.
- Tracked ticker state lives in `MarketDataService._tickers` and `MarketDataService._extra_tickers` in `backend/app/market/service.py`.
- Simulator state lives in `SimulatedMarketDataProvider._states` and random number generators in `backend/app/market/simulator.py`.
- Massive provider health lives in `MassiveMarketDataProvider._health` in `backend/app/market/massive.py`.

## Key Abstractions

**MarketDataProvider:**
- Purpose: Provider contract for latest prices, previous-day bars, and health.
- Examples: `backend/app/market/provider.py`, `backend/app/market/simulator.py`, `backend/app/market/massive.py`.
- Pattern: `typing.Protocol` with async methods and provider-independent return dataclasses.

**MarketDataService:**
- Purpose: Own the polling loop and present a cache-backed market data service to routes and future consumers.
- Examples: `backend/app/market/service.py`, `backend/app/main.py`, `backend/app/api/market.py`, `backend/app/api/stream.py`.
- Pattern: Lifespan-managed application service stored on `app.state`.

**PriceCache:**
- Purpose: Shared source of truth for current prices, stale marking, and previous tick comparison.
- Examples: `backend/app/market/cache.py`, `backend/app/api/market.py`, `backend/app/api/stream.py`.
- Pattern: In-memory repository guarded by `asyncio.Lock`.

**Provider-Independent Market Models:**
- Purpose: Keep REST, SSE, service, simulator, and Massive code using the same quote/bar/health vocabulary.
- Examples: `backend/app/market/models.py`, `backend/app/market/serialization.py`.
- Pattern: Frozen dataclasses with computed properties for change, change percent, and tick direction.

**Serialization Boundary:**
- Purpose: Keep API payload shape outside of provider/domain classes.
- Examples: `backend/app/market/serialization.py`, `backend/app/api/market.py`, `backend/app/api/stream.py`.
- Pattern: Small pure helper functions returning JSON-compatible dictionaries.

**Ticker Validation Boundary:**
- Purpose: Normalize and validate ticker strings in one shared module.
- Examples: `backend/app/market/validation.py`, `backend/app/api/market.py`, `backend/app/market/service.py`, `backend/app/market/massive.py`.
- Pattern: Regex-backed helpers reused before provider/cache operations.

## Entry Points

**ASGI Application:**
- Location: `backend/app/main.py`
- Triggers: `uv run uvicorn app.main:app --reload` from `backend/`.
- Responsibilities: App construction, lifespan setup/teardown, router inclusion, `/api/health`.

**App Factory for Tests:**
- Location: `backend/app/main.py`
- Triggers: `create_app(Settings(...))` from `backend/tests/test_api.py`.
- Responsibilities: Build an isolated FastAPI app with test settings.

**Market REST API:**
- Location: `backend/app/api/market.py`
- Triggers: HTTP requests under `/api/market`.
- Responsibilities: Price snapshot, single-symbol loading, market health, JSON errors.

**SSE Stream API:**
- Location: `backend/app/api/stream.py`
- Triggers: HTTP request to `/api/stream/prices`.
- Responsibilities: Long-lived event stream from `PriceCache`.

**Terminal Demo:**
- Location: `backend/market_data_demo.py`
- Triggers: `uv run python market_data_demo.py` from `backend/`.
- Responsibilities: Direct simulator polling, Rich UI rendering, 60-second market data demonstration.

**Pytest Suite:**
- Location: `backend/tests/`
- Triggers: `uv run pytest` from `backend/`.
- Responsibilities: Route, service, cache, provider factory, simulator, and Massive mapping verification.

## Architectural Constraints

- **Threading:** The backend uses a single asyncio event loop. Background refresh is one `asyncio.Task` created by `MarketDataService.start()` in `backend/app/market/service.py`.
- **Global state:** `settings = Settings()` is module-level in `backend/app/core/config.py`; `app = create_app()` is module-level in `backend/app/main.py`; service/cache instances are attached to `app.state` during lifespan in `backend/app/main.py`.
- **Circular imports:** Not detected across `backend/app/`; route modules import market helpers, and the app entry point imports route modules.
- **Persistence:** Not detected in implemented code. `PriceCache` in `backend/app/market/cache.py` is in-memory only.
- **Frontend/static serving:** Not detected in implemented code. No files are present under `fronted/`, and `backend/app/main.py` does not mount static assets.
- **Authentication:** Not detected in implemented code. Routes in `backend/app/api/` are unauthenticated.
- **Multi-process scaling:** `PriceCache` in `backend/app/market/cache.py` and `MarketDataService` in `backend/app/market/service.py` are per-process. Multiple Uvicorn workers do not share cache or tracked tickers.

## Anti-Patterns

### Direct Provider Calls From Consumers

**What happens:** Route handlers and future consumers can import `SimulatedMarketDataProvider` or `MassiveMarketDataProvider` directly from `backend/app/market/simulator.py` or `backend/app/market/massive.py`.
**Why it's wrong:** It bypasses `MarketDataService`, fragments tracked ticker state, and can create duplicate external API calls instead of using `PriceCache`.
**Do this instead:** Use `request.app.state.market_service.cache` from API adapters as shown in `backend/app/api/market.py`, or pass `MarketDataService` into new backend services from the composition point in `backend/app/main.py`.

### Route-Level Environment Parsing

**What happens:** New routes can read environment variables directly instead of using `Settings`.
**Why it's wrong:** It splits runtime configuration away from the tested app factory path in `backend/app/main.py` and makes test settings harder to override.
**Do this instead:** Add settings to `Settings` in `backend/app/core/config.py`, then inject them from `create_app()` in `backend/app/main.py`.

### Bare Array API Responses

**What happens:** New endpoints can return a top-level list of quotes or events.
**Why it's wrong:** Existing REST and SSE responses use JSON objects that leave room for metadata and keep contracts consistent.
**Do this instead:** Return object envelopes like `{"prices": [...]}` in `backend/app/api/market.py` and SSE payload objects in `backend/app/api/stream.py`.

### Swallowed Background Exceptions

**What happens:** `MarketDataService._run_loop()` catches all exceptions and suppresses them (`backend/app/market/service.py:103`).
**Why it's wrong:** Provider/cache bugs can be hidden from routes except through stale or missing data.
**Do this instead:** Keep provider-specific failures reflected through `MarketProviderHealth` as in `backend/app/market/massive.py`, and add structured logging or health state changes in `backend/app/market/service.py` before suppressing loop failures.

## Error Handling

**Strategy:** API input errors return FastAPI `HTTPException`; provider failures degrade provider health and return no quotes; cache reads mark stale data instead of failing.

**Patterns:**
- Invalid tickers raise `HTTPException(status_code=400, detail={"code": "INVALID_TICKER"})` in `backend/app/api/market.py`.
- Missing market data raises `HTTPException(status_code=404, detail={"code": "MARKET_DATA_UNAVAILABLE"})` in `backend/app/api/market.py`.
- Massive non-200 responses update `MarketProviderHealth` via `_mark_http_error()` in `backend/app/market/massive.py`.
- Massive network errors update `MarketProviderHealth` via `_mark_unhealthy()` in `backend/app/market/massive.py`.
- Cache staleness is encoded in `PriceQuote.stale` by `PriceCache._mark_stale()` in `backend/app/market/cache.py`.

## Cross-Cutting Concerns

**Logging:** Not detected in implemented code. `backend/app/market/service.py` suppresses loop exceptions without logging.
**Validation:** Shared ticker validation lives in `backend/app/market/validation.py`; API routes call it before loading unknown symbols.
**Authentication:** Not detected in implemented code. `backend/app/api/market.py`, `backend/app/api/stream.py`, and `backend/app/main.py` expose unauthenticated endpoints.
**Configuration:** Environment-backed settings live in `backend/app/core/config.py` and are consumed at app creation in `backend/app/main.py`.
**Serialization:** REST and SSE payloads use `backend/app/market/serialization.py` to preserve UTC timestamps, source, stale, session, volume, and OHLC fields.
**External API isolation:** Massive REST code is isolated to `backend/app/market/massive.py`; provider selection is isolated to `backend/app/market/provider.py`.

---

*Architecture analysis: 2026-07-31*
