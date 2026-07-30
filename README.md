# FinAlly

FinAlly is an AI-assisted simulated trading workstation. The current implemented slice is the market data backend: deterministic simulated prices by default, optional Massive REST market data when configured, cache-backed REST diagnostics, Server-Sent Events streaming, and a Rich terminal simulator demo.

Project documentation lives in `planning/`.

- Main product plan: `planning/PLAN.md`
- Current market data summary: `planning/MARKET_DATA_SUMMARY.md`
- Archived market data design/review notes: `planning/archive/`

## Backend

The backend is a Python `uv` project in `backend/`.

```bash
cd backend
uv run pytest
```

Latest market-data validation:

- `uv run pytest` -> `24 passed, 1 warning`
- `uv run python -m compileall app tests market_data_demo.py` -> passed

The warning is a third-party FastAPI/Starlette `TestClient` deprecation warning and does not affect test success.

## Market Data Demo

Run the interactive simulator dashboard:

```bash
cd backend
uv run python market_data_demo.py
```

The demo runs for 60 seconds or until Ctrl+C. It shows all 10 default tickers with live GBM-simulated prices, sparklines, direction arrows, notable-move events, and a final seed-vs-final session summary.

## Market Data API

Start the backend locally:

```bash
cd backend
uv run uvicorn app.main:app --reload
```

Useful endpoints:

- `GET /api/health`
- `GET /api/market/health`
- `GET /api/market/prices`
- `GET /api/market/prices/{ticker}`
- `GET /api/stream/prices`

By default the backend uses the simulator. Set `MASSIVE_API_KEY` to use the Massive REST provider.

## Configuration

Market data settings are read by `backend/app/core/config.py` from `.env` or `../.env`.

- `MASSIVE_API_KEY`
- `MARKET_POLL_INTERVAL_SECONDS`
- `MARKET_STALE_AFTER_SECONDS`
- `MARKET_SIMULATOR_SEED`

Empty `MASSIVE_API_KEY` means simulator mode. Non-empty `MASSIVE_API_KEY` means Massive mode; the backend does not silently fall back to simulated prices if Massive fails.
