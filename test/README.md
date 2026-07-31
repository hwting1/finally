# FinAlly E2E Tests

Playwright tests cover the single-container user flows from `planning/PLAN.md`.

The E2E suite runs in deterministic mode:

- `MASSIVE_API_KEY=` uses simulated market data.
- `LLM_MOCK=true` avoids live provider calls.

## Run Against A Local App

Start the app first:

```bash
FINALLY_PORT=18000 MASSIVE_API_KEY= LLM_MOCK=true LLM_API_KEY= docker compose up -d --build
```

Then run Playwright from this directory:

```bash
npm install
FINALLY_BASE_URL=http://localhost:18000 npm test
```

Useful variants:

```bash
npm run test:headed
npm run test:ui
```

If browsers are missing:

```bash
npm run install:browsers
```

## Run The Containerized Test Stack

From the repository root:

```bash
docker compose -f test/docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from playwright
```

This stack builds the app, waits for `/api/health`, then runs Playwright in the official Playwright container.

## Environment

| Variable | Default In Test Stack | Meaning |
|---|---:|---|
| `FINALLY_BASE_URL` | `http://app:8000` | App URL used by Playwright. |
| `LLM_MOCK` | `true` | Uses deterministic chat behavior. |
| `MASSIVE_API_KEY` | empty | Uses deterministic market simulator. |

Do not use live market-data or LLM credentials for the standard E2E suite. Live-provider checks should be run manually and kept separate from reproducible regression tests.
