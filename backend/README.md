# FinAlly Backend

This is the Python backend for FinAlly. It currently implements the market data foundation for the trading workstation:

- deterministic simulator by default
- optional Massive REST provider with `MASSIVE_API_KEY`
- shared current-price cache
- background market data refresh service
- market REST diagnostics
- Server-Sent Events price stream
- Rich terminal simulator demo

For the full market data build summary, see `../planning/MARKET_DATA_SUMMARY.md`.

## Requirements

- Python 3.11+
- `uv`

Install and run commands from this directory:

```bash
cd backend
```

## Run Tests

```bash
uv run pytest
```

Current expected result:

```text
24 passed, 1 warning
```

The warning is a third-party FastAPI/Starlette `TestClient` deprecation warning about `httpx`; it does not indicate a failing backend test.

## Run The API

```bash
uv run uvicorn app.main:app --reload
```

Useful endpoints:

- `GET /api/health`
- `GET /api/market/health`
- `GET /api/market/prices`
- `GET /api/market/prices/{ticker}`
- `GET /api/stream/prices`

The SSE endpoint emits `prices` events when quotes are available and `heartbeat` events when the cache is empty.

## Run The Terminal Demo

```bash
uv run python market_data_demo.py
```

The demo runs for 60 seconds or until Ctrl+C. It shows the 10 default tickers with GBM-simulated prices, direction arrows, sparklines, color-coded changes, notable-move events, and a final seed-vs-final summary.

## Configuration

Settings are defined in `app/core/config.py` and are loaded from `.env` and `../.env`.

| Variable | Default | Meaning |
|---|---:|---|
| `MASSIVE_API_KEY` | empty | Empty uses the simulator; non-empty uses Massive REST. |
| `MARKET_POLL_INTERVAL_SECONDS` | provider default | Overrides market polling cadence. |
| `MARKET_STALE_AFTER_SECONDS` | `30.0` | Age after which cached quotes are marked stale. |
| `MARKET_SIMULATOR_SEED` | `42` | Deterministic simulator seed. |

Massive mode never silently falls back to simulated prices after startup. If Massive authentication, rate limits, or network errors occur, provider health becomes degraded and existing cached values remain available.

## Market Data Architecture

Main modules:

- `app/main.py`: FastAPI app factory and lifespan wiring.
- `app/api/market.py`: REST market diagnostics.
- `app/api/stream.py`: SSE price streaming.
- `app/core/config.py`: environment-backed settings.
- `app/market/models.py`: provider-independent quote, bar, and health models.
- `app/market/provider.py`: provider protocol and provider factory.
- `app/market/simulator.py`: deterministic simulated market provider.
- `app/market/massive.py`: Massive REST provider and response mapping.
- `app/market/cache.py`: shared current-price cache.
- `app/market/service.py`: tracked ticker set and refresh loop.
- `app/market/serialization.py`: API/SSE payload serialization.
- `app/market/validation.py`: ticker normalization and validation.

Downstream services should read current prices from `MarketDataService.cache`. They should not call providers directly.

## Validation Commands

```bash
uv run pytest
uv run python -m compileall app tests market_data_demo.py
uv run python -c "import market_data_demo; print(len(market_data_demo.TICKERS), market_data_demo.RUN_SECONDS)"
```
