# Market Data Backend Code Review

Review date: 2026-07-30

## Scope Reviewed

I read all current planning documentation in `planning/`:

- `PLAN.md`
- `MARKET_DATA_DESIGN.md`
- `MARKET_INTERFACE.md`
- `MARKET_SIMULATOR.md`
- `MASSIVE_API.md`

I reviewed the implemented backend market data code:

- `backend/app/market/models.py`
- `backend/app/market/provider.py`
- `backend/app/market/simulator.py`
- `backend/app/market/__init__.py`
- `backend/tests/test_simulator.py`
- `backend/pyproject.toml`

## Test Results

Command run:

```bash
cd backend && uv run pytest
```

Result:

```text
9 passed in 0.06s
```

The first sandboxed attempt failed because `uv` could not write its normal cache under `/home/hwting/.cache/uv` from the restricted environment. The same test command passed when rerun with normal filesystem access.

## Executive Summary

The implemented simulator slice is small, readable, deterministic, and covered by focused unit tests. The `PriceQuote`, `DailyBar`, `MarketProviderHealth`, provider protocol, and simulator broadly match the planning documents for the in-memory default provider.

However, this is not yet the comprehensive Market Data backend described in `planning/MARKET_DATA_DESIGN.md`. The repository currently lacks the price cache, service loop, provider factory/configuration, FastAPI lifecycle integration, SSE endpoint, REST diagnostics, Massive adapter, serialization layer, and integration tests. Those are not polish items; they are required for downstream watchlist, portfolio valuation, market-order fills, and frontend streaming.

## Findings

### Critical: Market Data backend is not yet integrated into the application

The planning documents define a backend market data system centered on a `PriceCache`, `MarketDataService`, provider factory, FastAPI lifespan wiring, `/api/stream/prices`, and cache-backed REST/portfolio consumers. None of those modules or routes exist in `backend/` yet.

Evidence:

- `backend/` contains only `app/market/models.py`, `provider.py`, `simulator.py`, package init files, tests, and `pyproject.toml`.
- There is no `backend/app/market/cache.py`.
- There is no `backend/app/market/service.py`.
- There is no `backend/app/market/serialization.py`.
- There is no `backend/app/core/config.py`.
- There is no `backend/app/main.py`.
- There is no `backend/app/api/stream.py` or `backend/app/api/market.py`.

Impact:

The simulator can be called directly in tests, but the application cannot yet stream prices, maintain a shared current-price cache, fill trades from the same price shown to the UI, or expose market health.

Recommended fix:

Implement the next design steps from `MARKET_DATA_DESIGN.md`: settings, provider factory/default intervals, `PriceCache`, `MarketDataService`, serializer, FastAPI lifespan wiring, and `/api/stream/prices`. Add integration tests proving that the simulator path emits SSE prices within one second and that REST/portfolio consumers read from cache rather than calling providers directly.

### High: Massive provider selection and non-fallback behavior are not implemented

The plan requires `MASSIVE_API_KEY` to select a Massive REST provider once at startup, with bad keys producing degraded health rather than silently falling back to simulator. The current `provider.py` defines only the protocol; there is no `create_market_provider()`, `default_poll_interval_seconds()`, settings object, or `MassiveMarketDataProvider`.

Impact:

The environment-variable-driven provider behavior documented in `PLAN.md`, `MARKET_INTERFACE.md`, and `MARKET_DATA_DESIGN.md` is absent. A maker setting `MASSIVE_API_KEY` would have no effect because there is no application wiring to read it.

Recommended fix:

Add centralized market settings and a provider factory. Even if the Massive adapter remains a later optional implementation, tests should lock down that an empty key selects simulator and a non-empty key does not silently select simulator.

### Medium: Default simulator seed prices do not cover the full planned default watchlist

`PLAN.md` defines the default watchlist as:

```text
AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX
```

`backend/app/market/simulator.py` defines seed prices for:

```text
AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA, NFLX, AMD, SPY
```

This means `JPM` and `V`, which are planned first-launch watchlist tickers, will use the deterministic unknown-ticker fallback instead of realistic static seed prices. Conversely, `AMD` and `SPY` have explicit seeds but are not in the current default watchlist in `PLAN.md`.

Impact:

The first-launch experience can show unrealistic prices for planned default tickers. This also makes the simulator contract drift from the product plan.

Recommended fix:

Align `DEFAULT_SEED_PRICES` with the default watchlist, or deliberately document that `AMD`/`SPY` are also seeded extension symbols. Add a test that every `PLAN.md` default watchlist ticker has an explicit seed price.

### Medium: Ticker validation is not implemented in the current backend slice

The plan’s core ticker rule is `^[A-Z]{1,5}$` after trimming and uppercasing. The simulator currently normalizes non-empty strings but does not validate the resulting symbol shape. For example, a provider call could create deterministic state for symbols containing punctuation or more than five letters.

Impact:

This may be acceptable if future API/service layers validate before calling providers, but that layer does not exist yet. Until it does, invalid symbols can enter simulator state if any caller passes them through.

Recommended fix:

Put ticker validation at the API/service boundary once those modules exist. Consider also adding a small shared `normalize_ticker()` / `validate_ticker()` helper so watchlist, portfolio trades, LLM actions, and market service all use the same rule.

### Low: Initial simulator `previous_close` does not match the design examples exactly

The planning examples initialize simulator `previous_close` to the seed price. The implementation initializes it to a deterministic random value within roughly +/-2% of the seed price.

Impact:

This creates a non-zero daily change on the first emitted quote, which may be more visually interesting, but it differs from the documented blueprint. It is not currently harmful and is deterministic.

Recommended fix:

Either change `previous_close` to the seed price or update the planning docs/tests to explicitly allow deterministic prior-close variation.

## Positive Notes

- The domain models are immutable, slotted dataclasses where appropriate.
- `PriceQuote.change`, `change_percent`, and `direction` are simple and provider-independent.
- The simulator uses per-ticker RNGs plus sorted ticker normalization, so same seed and same request sequence are reproducible.
- The simulator avoids global randomness and supports an injectable clock, which makes tests deterministic.
- Prices are floored and per-tick returns are bounded.
- Previous-day bars preserve valid OHLC relationships and skip weekends.
- The simulator does not import Massive code and does not perform network I/O.

## Test Coverage Assessment

Current tests cover the implemented simulator well:

- Determinism for same seed and ticker sequence
- Unknown ticker seed stability
- Positive and bounded prices
- Previous price continuity
- Day high/low behavior
- Previous-day OHLC validity
- Health status
- Empty ticker input
- Weekend handling for previous-day bars
- Invalid update interval

Missing tests relative to the planning contract:

- Provider factory selection with and without `MASSIVE_API_KEY`
- Default poll interval selection
- Price cache previous-price preservation and staleness marking
- Market service tracked ticker universe
- SSE initial snapshot, update batch, and heartbeat behavior
- Serializer payload shape
- Market REST diagnostics
- Massive fixture parsing and fallback order
- Massive auth/rate-limit/degraded health behavior
- Trade fill path reading from cache rather than calling a provider
- Add-watchlist/add-trade path making a new ticker available in the next price batch

## Conclusion

The implemented code is a solid simulator foundation, and the current unit tests pass. I do not see correctness issues in the simulator severe enough to block building on it.

The main conclusion is that the Market Data backend is only partially implemented. Before frontend or portfolio agents depend on it, the project needs the cache/service/API wiring and at least simulator-backed integration tests for `/api/stream/prices` and cache-based current-price reads. Massive can remain optional, but provider selection and non-fallback behavior should be locked down early so the environment-variable contract does not drift.
