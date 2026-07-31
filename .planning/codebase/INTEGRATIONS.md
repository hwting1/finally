# External Integrations

**Analysis Date:** 2026-07-31

## APIs & External Services

**Market Data:**
- Massive REST API - Optional real equity market data provider enabled by `MASSIVE_API_KEY`.
  - SDK/Client: direct `httpx.AsyncClient` calls in `backend/app/market/massive.py`; no official Massive SDK is used.
  - Auth: `MASSIVE_API_KEY`, read by `backend/app/core/config.py` and passed to `MassiveMarketDataProvider` by `backend/app/market/provider.py`.
  - Base URL: `https://api.massive.com` in `backend/app/market/massive.py`.
  - Snapshot endpoint: `GET /v2/snapshot/locale/us/markets/stocks/tickers` in `backend/app/market/massive.py`.
  - Previous-day bars endpoint: `GET /v2/aggs/ticker/{ticker}/prev` in `backend/app/market/massive.py`.
  - Credential transport: `Authorization: Bearer` header built in `backend/app/market/massive.py`.

**Local Simulator:**
- Deterministic in-process market simulator - Default provider when `MASSIVE_API_KEY` is empty.
  - SDK/Client: Not applicable; implemented in `backend/app/market/simulator.py`.
  - Auth: Not applicable.
  - Seed: `MARKET_SIMULATOR_SEED` from `backend/app/core/config.py`.

**LLM Providers:**
- OpenAI-compatible LLM provider - Planned in `planning/PLAN.md` and project skill `.codex/skills/openai-compatible-llm/SKILL.md`.
  - SDK/Client: Not detected in current backend dependencies or imports; `openai` is not declared in `backend/pyproject.toml`.
  - Auth: Planned `LLM_API_KEY` in `planning/PLAN.md`; not implemented in `backend/app/core/config.py`.
  - Base URL: Planned `LLM_BASE_URL` in `planning/PLAN.md`; not implemented in current backend code.

## Data Storage

**Databases:**
- Not detected in current implementation.
  - Connection: No database connection environment variable is implemented in `backend/app/core/config.py`.
  - Client: No ORM, SQL client, migration tool, or database package is declared in `backend/pyproject.toml`.
  - Current state: market data is stored in an in-memory `dict[str, PriceQuote]` protected by `asyncio.Lock` in `backend/app/market/cache.py`.

**File Storage:**
- Local filesystem only for source code, documentation, and uv dependency metadata.
  - Runtime file-backed persistence: Not detected in `backend/app/`.
  - Market data persistence: Not detected; `PriceCache` in `backend/app/market/cache.py` is process memory only.

**Caching:**
- In-memory latest-price cache in `backend/app/market/cache.py`.
  - Owner: `PriceCache` in `backend/app/market/cache.py`.
  - Writer: `MarketDataService.refresh_once()` in `backend/app/market/service.py`.
  - Readers: REST diagnostics in `backend/app/api/market.py` and SSE stream in `backend/app/api/stream.py`.
  - External cache: Redis/Memcached not detected in `backend/pyproject.toml` or `backend/app/`.

## Authentication & Identity

**Auth Provider:**
- Not detected for user authentication.
  - Implementation: No login/session/JWT/OAuth middleware is present in `backend/app/main.py` or `backend/app/api/`.
  - API auth: Massive outbound authentication only, implemented with bearer-token headers in `backend/app/market/massive.py`.

## Monitoring & Observability

**Error Tracking:**
- None detected.
  - No Sentry, OpenTelemetry, Datadog, New Relic, or similar package is declared in `backend/pyproject.toml`.

**Logs:**
- No application logging framework detected in `backend/app/`.
- `MarketDataService._run_loop()` suppresses background refresh exceptions with `except Exception: pass` in `backend/app/market/service.py`.
- Provider health is exposed through structured health objects from `backend/app/market/models.py`, serialized by `backend/app/market/serialization.py`, and returned by `GET /api/market/health` in `backend/app/api/market.py`.
- Terminal-only visual output uses Rich in `backend/market_data_demo.py`.

## CI/CD & Deployment

**Hosting:**
- Not detected in current repository files.
  - Current app entrypoint: `backend/app/main.py`.
  - Planned container deployment appears in `planning/PLAN.md`, but no `Dockerfile`, `docker-compose.yml`, `deploy/`, or platform config is present in the current file set.

**CI Pipeline:**
- None detected.
  - `.github/` directory exists at `.github/`, but no workflow files were detected under `.github/`.

## Environment Configuration

**Required env vars:**
- None required for default simulator mode.
- Optional `MASSIVE_API_KEY` in `backend/app/core/config.py` enables Massive REST mode.
- Optional `MARKET_POLL_INTERVAL_SECONDS` in `backend/app/core/config.py` overrides provider polling cadence.
- Optional `MARKET_STALE_AFTER_SECONDS` in `backend/app/core/config.py` controls quote staleness thresholds.
- Optional `MARKET_SIMULATOR_SEED` in `backend/app/core/config.py` controls deterministic simulator state.
- Planned but not implemented: `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_MOCK` in `planning/PLAN.md`.

**Secrets location:**
- `.env` file present at repo root as `.env`; contents were not read.
- `.gitignore` ignores `.env`, `.envrc`, `.venv`, `env/`, `venv/`, `.pypirc`, and other local/cache files.
- `backend/app/core/config.py` reads settings from `../.env` and `.env` relative to backend execution context.

## Webhooks & Callbacks

**Incoming:**
- None detected.
  - Current HTTP routes are health, market diagnostics, and SSE: `backend/app/main.py`, `backend/app/api/market.py`, and `backend/app/api/stream.py`.
  - No webhook route naming or signature-validation logic detected in `backend/app/api/`.

**Outgoing:**
- Massive REST polling only.
  - Snapshot polling happens through `MassiveMarketDataProvider.get_prices()` in `backend/app/market/massive.py`.
  - Previous-day bar lookups happen through `MassiveMarketDataProvider.get_previous_day_bars()` in `backend/app/market/massive.py`.
  - No outgoing webhook delivery, queue, email, Slack, or callback client detected in `backend/app/` or `backend/pyproject.toml`.

---

*Integration audit: 2026-07-31*
