# FinAlly E2E Tests

Playwright tests for the project-level contracts in `planning/PLAN.md`. These files live under `test/` so they can be developed independently while `frontend/`, `backend/`, Docker, and scripts are still being built.

## Expected App Contracts

The tests intentionally use stable `data-testid` selectors that the frontend should implement:

- `app-shell`, `watchlist-panel`, `trade-bar`, `portfolio-summary`, `positions-table`, `chat-panel`
- `connection-status` with `data-state="connected" | "reconnecting" | "disconnected"`
- `watchlist-row-{TICKER}`, with nested `watchlist-price`
- `portfolio-cash`, `portfolio-total`, `portfolio-heatmap`, `portfolio-pnl-chart`
- `trade-ticker-input`, `trade-quantity-input`, `buy-button`, `sell-button`, `trade-status`
- `position-row-{TICKER}`, with nested `position-quantity`
- `chat-input`, `chat-send-button`, `chat-disabled-message`, `chat-message-assistant`, `chat-action-result`

The backend/API contracts assumed by the tests are:

- `GET /` serves the exported frontend through FastAPI at `http://localhost:8000`
- `GET /api/stream/prices` drives the watchlist through `EventSource`
- manual trades update cash, positions, portfolio total, heatmap, and P&L chart
- missing `LLM_API_KEY` with `LLM_MOCK=false` disables chat without blocking the rest of the app
- `LLM_MOCK=true` returns deterministic chat responses and action results

## Local Run

Start the app separately, then run:

```bash
cd test
npm install
npm run install:browsers
FINALLY_BASE_URL=http://localhost:8000 npm test
```

To exercise mock chat:

```bash
cd test
LLM_MOCK=true FINALLY_BASE_URL=http://localhost:8000 npm test
```

To exercise disabled chat, run the app with no `LLM_API_KEY` and `LLM_MOCK=false`, then:

```bash
cd test
LLM_MOCK=false FINALLY_BASE_URL=http://localhost:8000 npm test -- chat.spec.ts
```

## Docker Runner

Once the project `Dockerfile` exists and serves the full app on port 8000:

```bash
docker compose -f test/docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from playwright
docker compose -f test/docker-compose.test.yml down -v
```

## Current Blockers

- The current repo slice does not yet contain the planned `Dockerfile`, `scripts/`, or complete frontend app.
- The current FastAPI app exposes market data endpoints, but not portfolio, watchlist CRUD, chat, static frontend serving, or the selector-bearing UI these tests target.
- Until those pieces land, these E2E tests are expected to fail at first-launch UI assertions or require a separately running implementation branch.
