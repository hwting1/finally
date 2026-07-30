# Backend Agent Instructions

This directory contains the FinAlly backend Python project.

## Scope

Backend code owns:

- FastAPI application startup and API routes.
- Market data providers, cache, service loop, and serialization.
- Backend tests under `backend/tests`.
- Backend-only scripts such as `market_data_demo.py`.

Project-wide documentation remains in `../planning`.

## Commands

Run backend tests from this directory:

```bash
uv run pytest
```

Run a compile check:

```bash
uv run python -m compileall app tests market_data_demo.py
```

Run the terminal market-data demo:

```bash
uv run python market_data_demo.py
```

Run the API server:

```bash
uv run uvicorn app.main:app --reload
```

## Market Data Rules

- Use `MarketDataService.cache` as the source of truth for current prices.
- Do not call market providers directly from portfolio, watchlist, frontend, or LLM context code.
- Empty `MASSIVE_API_KEY` selects the simulator.
- Non-empty `MASSIVE_API_KEY` selects Massive and must not fall back to simulator after startup.
- Normalize tickers by trimming and uppercasing.
- Validate core ticker symbols with `^[A-Z]{1,5}$`.
- Keep SSE payloads and REST responses JSON-object based, not bare arrays.
- Preserve `source`, `stale`, and UTC timestamp fields for UI and LLM consumers.

## Dependency Rules

- Update `pyproject.toml` and `uv.lock` together when adding or changing backend dependencies.
- Prefer small, explicit dependencies.
- Keep tests deterministic; use `httpx.MockTransport` for Massive provider tests.

## Documentation Rules

- Update `../planning/MARKET_DATA_SUMMARY.md` when changing market data behavior.
- Keep older market-data design notes in `../planning/archive/`.
