# FinAlly Backend

FastAPI service for the FinAlly trading workstation.

## Responsibilities

- Serve API routes and the built frontend static files when available.
- Maintain SQLite-backed watchlist, portfolio, trades, snapshots, and chat history.
- Stream current prices over SSE from a shared `PriceCache`.
- Use the deterministic simulator when `MASSIVE_API_KEY` is empty.
- Use Massive REST market data when `MASSIVE_API_KEY` is non-empty.
- Execute manual trades and AI-requested actions through the same validation path.
- Call an OpenAI-compatible LLM provider for structured chat plans when live chat is enabled.

Massive mode is explicit: if a non-empty `MASSIVE_API_KEY` is configured, provider failures are reported instead of silently falling back to simulated prices.

## Run Locally

From this directory:

```bash
uv run uvicorn app.main:app --reload
```

Useful deterministic local run:

```bash
MASSIVE_API_KEY= LLM_MOCK=true uv run uvicorn app.main:app --reload
```

The backend reads settings from environment variables, `backend/.env`, and `../.env`.

## API

Core:

- `GET /`
- `GET /api/health`

Market data:

- `GET /api/market/health`
- `GET /api/market/prices`
- `GET /api/market/prices/{ticker}`
- `GET /api/stream/prices`

Watchlist:

- `GET /api/watchlist`
- `POST /api/watchlist`
- `DELETE /api/watchlist/{ticker}`

Portfolio:

- `GET /api/portfolio`
- `POST /api/portfolio/trade`

AI chat:

- `POST /api/chat`

OpenAPI docs are available at `/docs` when running the backend.

## Configuration

| Variable | Default | Meaning |
|---|---:|---|
| `DATABASE_PATH` | `../db/finally.db` | SQLite database path. |
| `MASSIVE_API_KEY` | empty | Empty uses simulator; non-empty uses Massive REST. |
| `MARKET_POLL_INTERVAL_SECONDS` | provider default | Optional polling cadence override. |
| `MARKET_STALE_AFTER_SECONDS` | `30.0` | Age after which cached quotes are marked stale. |
| `MARKET_SIMULATOR_SEED` | `42` | Deterministic simulator seed. |
| `LLM_MOCK` | `false` | Enables deterministic mock chat actions without a provider key. |
| `LLM_API_KEY` | empty | Required for live chat when `LLM_MOCK=false`. |
| `LLM_BASE_URL` | Gemini OpenAI-compatible endpoint | Provider base URL for the OpenAI SDK. |
| `LLM_MODEL` | `gemini-3-flash-preview` | Structured-output model name; override for another available provider model. |
| `LLM_MAX_ACTIONS` | `5` | Maximum AI actions accepted per response. |
| `LLM_MAX_ORDER_NOTIONAL_PORTFOLIO_FRACTION` | `0.5` | Maximum AI order notional as a portfolio-value fraction. |

LLM behavior:

- `LLM_MOCK=true` returns deterministic local chat responses.
- `LLM_MOCK=false` with a non-empty `LLM_API_KEY` calls the configured live provider.
- `LLM_MOCK=false` with an empty `LLM_API_KEY` keeps the app running but disables chat with a structured configuration error.

## Tests

```bash
uv run pytest
```

Focused chat tests:

```bash
uv run pytest tests/test_llm_chat.py
```

Terminal market-data demo:

```bash
uv run python market_data_demo.py
```
