# Codebase Concerns

**Analysis Date:** 2026-07-31

## Tech Debt

**Silent market-data refresh failures:**
- Issue: `MarketDataService._run_loop()` catches every `Exception` and discards it with `pass`.
- Files: `backend/app/market/service.py:98`, `backend/app/market/service.py:103`
- Impact: Provider failures, ticker-loader errors, cache update errors, and future portfolio/watchlist integration failures can leave stale prices in `PriceCache` without any log, metric, health transition, or visible diagnostic. This weakens the contract that all consumers use `MarketDataService.cache` as the source of truth.
- Fix approach: Replace the broad silent catch in `backend/app/market/service.py` with structured logging and a service-level health/error field. Add a regression test in `backend/tests/test_cache_service_provider.py` using a provider or loader that raises and assert the error is visible through `GET /api/market/health`.

**Settings cover only market data while planned app settings are wider:**
- Issue: `Settings` only defines `massive_api_key`, market polling, stale threshold, and simulator seed.
- Files: `backend/app/core/config.py:8`, `backend/app/core/config.py:11`, `backend/app/core/config.py:14`, `planning/PLAN.md:122`, `planning/PLAN.md:153`
- Impact: Planned `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_MOCK`, SQLite path, and deployment settings have no centralized runtime contract yet. Future code may hard-code provider details or read environment variables directly in services, which conflicts with the project-local `openai-compatible-llm` skill.
- Fix approach: Extend `backend/app/core/config.py` before adding LLM, database, or deployment code. Keep all provider configuration in `Settings`, pass configured clients/models into services, and add settings tests that instantiate `Settings` with explicit values instead of depending on `.env`.

**Current repository includes dual agent-runtime trees:**
- Issue: Both `.claude/` and `.codex/` contain large command, agent, hook, and runtime metadata trees.
- Files: `.claude/gsd-file-manifest.json`, `.claude/settings.json`, `.codex/gsd-file-manifest.json`, `.codex/settings.json`
- Impact: Codebase scans and reviews are noisy, duplicated agent instructions can drift, and future changes may update one agent surface without the other. This is not application runtime debt, but it affects maintainability of project automation.
- Fix approach: Treat `.claude/` and `.codex/` as tool-owned directories. When changing workflow behavior, update the owning GSD installation path rather than editing individual generated files. Keep application code and planning docs separate from tool runtime metadata.

**Local generated directories are present in the working tree:**
- Issue: Ignored local runtime artifacts exist under `backend/.venv/`, `backend/.pytest_cache/`, `backend/app/__pycache__/`, and `backend/tests/__pycache__/`.
- Files: `backend/.venv/`, `backend/.pytest_cache/`, `backend/app/__pycache__/`, `backend/tests/__pycache__/`, `.gitignore`
- Impact: They are not tracked, but they inflate local scans and can hide source-level complexity if mapper/reviewer commands do not prune ignored directories.
- Fix approach: Keep `.gitignore` protections in place and prune `backend/.venv/`, `__pycache__/`, and `.pytest_cache/` in analysis scripts. Do not import code from `backend/.venv/`; use `backend/pyproject.toml` and `backend/uv.lock` as dependency sources.

## Known Bugs

**Potential startup failure with invalid poll interval environment value:**
- Symptoms: `MarketDataService.__init__()` raises `ValueError` when `poll_interval_seconds <= 0`, and `create_app()` constructs the service during FastAPI lifespan startup.
- Files: `backend/app/market/service.py:41`, `backend/app/market/service.py:43`, `backend/app/main.py:16`, `backend/app/main.py:21`, `backend/app/main.py:29`
- Trigger: Set `MARKET_POLL_INTERVAL_SECONDS=0` or a negative value and start `uv run uvicorn app.main:app --reload` from `backend/`.
- Workaround: Use a positive `MARKET_POLL_INTERVAL_SECONDS` value or leave it unset so `backend/app/market/provider.py:31` chooses the simulator or Massive default interval.

**Unknown future asset symbols are rejected by the core ticker regex:**
- Symptoms: Only uppercase alphabetic symbols of length 1-5 pass validation.
- Files: `backend/app/market/validation.py:8`, `backend/app/api/market.py:28`, `backend/app/api/market.py:30`
- Trigger: Request `/api/market/prices/BRK.B`, `/api/market/prices/BRK-B`, or longer listed symbols after future watchlist support expands beyond simple US equity tickers.
- Workaround: Use plain 1-5 letter stock tickers only. Extend `TICKER_PATTERN` and add API/provider tests before supporting class shares, ETFs with punctuation, crypto, or non-US symbols.

**Root route returns 404 because static frontend serving is not implemented:**
- Symptoms: `GET /` is not registered by the FastAPI app; only `/api/health`, `/api/market/*`, and `/api/stream/prices` are included.
- Files: `backend/app/main.py:35`, `backend/app/main.py:36`, `backend/app/main.py:37`, `backend/app/main.py:39`, `planning/PLAN.md:48`, `planning/PLAN.md:57`
- Trigger: Start the backend and visit `/` or refresh any planned frontend route.
- Workaround: Use API routes directly. Add static export serving in `backend/app/main.py` only after the planned frontend artifact exists.

## Security Considerations

**No authentication or authorization boundary exists:**
- Risk: All implemented API routes are public within whatever network exposes the FastAPI process. This is acceptable for the current simulator-only learning slice, but future trade, portfolio, and AI action endpoints would be unauthenticated if added using the current route pattern.
- Files: `backend/app/main.py:35`, `backend/app/api/market.py:19`, `backend/app/api/market.py:26`, `backend/app/api/stream.py:19`, `planning/PLAN.md:78`
- Current mitigation: The plan intentionally assumes no multi-user auth and simulated money. The current implemented endpoints expose only market diagnostics and SSE price data.
- Recommendations: Before adding portfolio mutation, trade execution, or AI action routes, document the no-auth scope in API contracts and add request validation, action limits, and structured audit records in the route/service layer. If the app is deployed beyond localhost or a classroom demo, add an explicit auth gate.

**Massive API key is held in provider instance memory and sent on every request:**
- Risk: The provider stores the raw key on `self._api_key` and injects it into the `Authorization` header for each Massive request.
- Files: `backend/app/market/massive.py:78`, `backend/app/market/massive.py:84`, `backend/app/market/massive.py:108`, `backend/app/market/massive.py:189`
- Current mitigation: The code does not log request headers or API keys. `.env` is ignored by `.gitignore`, and this audit noted `.env` existence only without reading contents.
- Recommendations: Keep provider logging sanitized. When adding HTTP diagnostics, never log `headers`, full `httpx.Request` objects, or environment values. Add tests for health messages that assert they do not include credential material.

**No rate limiting on dynamic ticker loading endpoints:**
- Risk: `GET /api/market/prices/{ticker}` adds valid unknown tickers to the in-memory tracked set and triggers an immediate refresh. A client can expand `_extra_tickers` and force repeated provider calls.
- Files: `backend/app/api/market.py:26`, `backend/app/api/market.py:33`, `backend/app/api/market.py:34`, `backend/app/api/market.py:35`, `backend/app/market/service.py:50`, `backend/app/market/service.py:75`
- Current mitigation: `backend/app/market/validation.py:8` limits symbols to 1-5 alphabetic characters, bounding the theoretical symbol space. The current simulator provider has no external cost.
- Recommendations: Before exposing Massive-backed deployments publicly, add per-client/request throttling, a maximum tracked ticker count, and a way to evict or reset dynamic tickers.

## Performance Bottlenecks

**SSE stream loops independently per connected client:**
- Problem: Each `/api/stream/prices` connection snapshots and serializes the full cache at `service.poll_interval_seconds`.
- Files: `backend/app/api/stream.py:23`, `backend/app/api/stream.py:25`, `backend/app/api/stream.py:30`, `backend/app/api/stream.py:32`, `backend/app/api/stream.py:39`
- Cause: The SSE generator has no shared broadcaster, diffing, backpressure handling, or capped client list. This is fine for a handful of development clients and 10 default tickers.
- Improvement path: Keep this pattern for the current slice. If multiple browsers or larger watchlists are expected, introduce a publisher task that serializes once per tick and broadcasts to subscribers, and emit deltas instead of the full snapshot where possible.

**Massive previous-day bar fetching is sequential:**
- Problem: `get_previous_day_bars()` calls `_fetch_previous_day_bar()` one symbol at a time.
- Files: `backend/app/market/massive.py:134`, `backend/app/market/massive.py:137`, `backend/app/market/massive.py:138`, `backend/app/market/massive.py:179`
- Cause: The implementation prioritizes simple request handling over concurrency or batching.
- Improvement path: Keep sequential calls while previous-day bars are not on the request path. If bars become UI-critical, batch when the provider API supports it or use bounded concurrency with explicit rate-limit handling.

**Tracked ticker set only grows during process lifetime:**
- Problem: Unknown valid tickers requested through `GET /api/market/prices/{ticker}` are added to `_extra_tickers` and retained until process restart.
- Files: `backend/app/api/market.py:33`, `backend/app/api/market.py:34`, `backend/app/market/service.py:50`, `backend/app/market/service.py:79`, `backend/app/market/service.py:80`
- Cause: There is no watchlist persistence, remove endpoint, TTL, or maximum ticker count.
- Improvement path: Add explicit watchlist CRUD backed by the planned database, then make `MarketDataService` load only persisted watchlist tickers plus bounded transient requests.

## Fragile Areas

**MarketDataService is the central coupling point for future portfolio, watchlist, and LLM features:**
- Files: `backend/app/market/service.py:35`, `backend/app/market/service.py:45`, `backend/app/market/service.py:87`, `backend/app/market/service.py:95`, `backend/AGENTS.md:35`
- Why fragile: Current behavior is intentionally small: load static tickers, refresh provider, update cache, expose provider health. Future database-backed watchlists, portfolio fills, and AI context construction will depend on the same cache and refresh loop.
- Safe modification: Keep provider calls inside `MarketDataService`; do not call providers directly from new routes or LLM/portfolio services. Add tests in `backend/tests/test_cache_service_provider.py` for every new service-level contract before wiring it to API routes.
- Test coverage: Existing tests cover loader union, dynamic ticker additions, cache updates, and provider selection. They do not cover refresh-loop exception visibility, service restart semantics, concurrent add/refresh behavior, or process shutdown under active SSE clients.

**Massive payload parsing depends on third-party response shape details:**
- Files: `backend/app/market/massive.py:45`, `backend/app/market/massive.py:105`, `backend/app/market/massive.py:113`, `backend/app/market/massive.py:120`, `backend/tests/test_massive.py:14`, `backend/tests/test_massive.py:39`
- Why fragile: Price selection depends on `lastTrade`, `lastQuote`, `min`, `day`, `prevDay`, nanosecond timestamps, and millisecond timestamps. Provider schema drift or partial responses can silently drop quotes.
- Safe modification: Add focused fixtures to `backend/tests/test_massive.py` for every new Massive field or fallback branch. Keep parsing isolated in `backend/app/market/massive.py` and convert third-party payloads into `PriceQuote` before they touch cache or routes.
- Test coverage: Existing tests cover fallback order, successful snapshot mapping, auth failure, and previous-day bar mapping. They do not cover malformed JSON, non-HTTP parsing exceptions, missing `tickers`, partial ticker failures, rate-limit recovery, or server-error recovery.

**Environment-file loading depends on process working directory:**
- Files: `backend/app/core/config.py:8`, `backend/app/core/config.py:9`, `README.md:40`, `README.md:57`
- Why fragile: `SettingsConfigDict(env_file=("../.env", ".env"))` resolves relative paths from the current working directory. `cd backend && uv run uvicorn app.main:app --reload` reads project-root `.env` and backend `.env`; starting from a different directory may not.
- Safe modification: Resolve env files from `backend/app/core/config.py` using an absolute project/backend path if startup commands diversify. Keep tests constructing `Settings(...)` explicitly to avoid accidental dependence on developer-local `.env`.
- Test coverage: Existing tests instantiate `Settings` manually in `backend/tests/test_api.py`. There is no test for env-file path resolution.

**API error shape is not centralized:**
- Files: `backend/app/api/market.py:29`, `backend/app/api/market.py:30`, `backend/app/api/market.py:37`, `backend/app/api/market.py:38`, `planning/PLAN.md:568`
- Why fragile: Current errors return ad hoc FastAPI `detail` dictionaries. The plan calls for shared API schemas and error shape before broader frontend and portfolio work.
- Safe modification: Introduce a shared error helper or Pydantic response model before adding trade, chat, or database endpoints. Update existing market routes and tests first so future endpoints reuse the same shape.
- Test coverage: Existing API tests verify invalid ticker status code but not full error schema stability.

## Scaling Limits

**In-memory cache and watchlist are single-process only:**
- Current capacity: The implemented default watchlist has 10 tickers in `backend/app/market/service.py:15`, with in-memory quotes in `backend/app/market/cache.py:11`.
- Limit: Multiple Uvicorn workers, container restarts, or future horizontal scaling will not share cache, dynamic tickers, or provider health. Requested tickers disappear on restart.
- Scaling path: Keep single-process for the current learning slice. When persistence lands, move watchlist and portfolio state to SQLite as planned and treat `PriceCache` as ephemeral derived state.

**Massive polling may exceed URL/rate constraints with unbounded ticker sets:**
- Current capacity: Massive defaults to a 15-second poll interval when `MASSIVE_API_KEY` is set and no override exists.
- Limit: `backend/app/market/massive.py:105` sends a comma-separated sorted ticker list in one query parameter. Large `_extra_tickers` sets can make long URLs or provider-rejected requests, while low `MARKET_POLL_INTERVAL_SECONDS` values can hit rate limits.
- Scaling path: Add a maximum tracked ticker count, chunk Massive requests when needed, and validate poll intervals against provider tier guidance before startup.

## Dependencies at Risk

**Unneeded `httpx2` dependency is installed:**
- Risk: `backend/pyproject.toml` includes `httpx2`, but source files import `httpx`, not `httpx2`.
- Impact: Extra dependency surface increases install time, lockfile size, audit noise, and potential vulnerability exposure without visible runtime benefit.
- Migration plan: Remove `httpx2` from `backend/pyproject.toml` and update `backend/uv.lock` if no script or planned tool uses it. Re-run `cd backend && uv run pytest` and compile checks after removal.

**No enforced lint command in project metadata:**
- Risk: `backend/pyproject.toml` configures Ruff line length and target version but does not include Ruff in dev dependencies or a committed command wrapper.
- Impact: Style drift and unused imports can land without automated feedback. Future agents may assume `ruff` exists because `[tool.ruff]` is present.
- Migration plan: Add `ruff` to the `dev` dependency group in `backend/pyproject.toml`, update `backend/uv.lock`, and document `uv run ruff check .` in `backend/AGENTS.md` only after the command passes.

## Missing Critical Features

**Frontend application is not present:**
- Problem: The plan describes a Next.js static export with watchlist, charts, portfolio views, trade bar, and AI chat, but no `frontend/` directory exists in the current repo.
- Blocks: First-launch UI acceptance, SSE reconnect UI, price flash animations, portfolio heatmap, positions table, and static serving through FastAPI.
- Files: `planning/PLAN.md:65`, `planning/PLAN.md:87`, `planning/PLAN.md:112`, `planning/PLAN.md:443`, `planning/PLAN.md:455`, `backend/app/main.py:35`

**SQLite persistence and portfolio/trade backend are not present:**
- Problem: The plan calls for SQLite persistence, portfolio snapshots, trade execution, watchlist CRUD, and database initialization, but the current backend only implements market data.
- Blocks: Cash balance, buy/sell orders, positions table, P&L calculations, persisted watchlist, AI action audit, and restart survival.
- Files: `planning/PLAN.md:60`, `planning/PLAN.md:67`, `planning/PLAN.md:91`, `planning/PLAN.md:114`, `planning/PLAN.md:528`, `planning/PLAN.md:561`, `backend/app/api/market.py`

**LLM/chat integration is not implemented:**
- Problem: The plan describes OpenAI-compatible LLM settings, mock mode, structured output parsing, chat persistence, automatic trade/watchlist actions, and guardrails. Current settings and routes have no LLM fields or chat endpoint.
- Blocks: AI assistant panel, mocked E2E chat, disabled-chat configuration response, structured action validation, and action audit display.
- Files: `planning/PLAN.md:69`, `planning/PLAN.md:124`, `planning/PLAN.md:147`, `planning/PLAN.md:371`, `planning/PLAN.md:386`, `planning/PLAN.md:415`, `backend/app/core/config.py`

**Container, platform scripts, and E2E harness are not present:**
- Problem: The plan requires a single-container launch path, start/stop scripts, Dockerfile, docker-compose wrapper, and Playwright E2E tests, but the repo currently contains only the backend project and planning docs.
- Blocks: First-launch acceptance, static app serving validation, browser-level SSE reconnect tests, and classroom-friendly one-command startup.
- Files: `planning/PLAN.md:48`, `planning/PLAN.md:95`, `planning/PLAN.md:100`, `planning/PLAN.md:103`, `planning/PLAN.md:541`, `planning/PLAN.md:558`, `README.md:40`

**Committed `.env.example` is not present:**
- Problem: The plan says `.env.example` should be committed with safe defaults, but the root file listing contains `.env` only as an ignored local file and no `.env.example`.
- Blocks: Reproducible setup for new developers and explicit documentation of supported environment variables.
- Files: `planning/PLAN.md:105`, `planning/PLAN.md:155`, `.gitignore`, `backend/app/core/config.py:9`

## Test Coverage Gaps

**SSE behavior is not covered by tests:**
- What's not tested: `/api/stream/prices` event framing, heartbeat behavior before initial cache fill, disconnect behavior, reconnect assumptions, and serialization cadence.
- Files: `backend/app/api/stream.py:19`, `backend/app/api/stream.py:23`, `backend/app/api/stream.py:32`, `backend/tests/test_api.py`
- Risk: Frontend `EventSource` integration can break due to malformed event output or timing issues without pytest failures.
- Priority: High before frontend integration.

**Provider failure recovery is only partially covered:**
- What's not tested: Massive `429`, `5xx`, network exceptions, malformed JSON, health recovery after a later success, cache behavior after provider returns no quotes, and service health when the refresh loop catches exceptions.
- Files: `backend/app/market/massive.py:110`, `backend/app/market/massive.py:114`, `backend/app/market/massive.py:221`, `backend/app/market/service.py:98`, `backend/tests/test_massive.py`
- Risk: Real-data mode can degrade silently or recover incorrectly while simulator-mode tests still pass.
- Priority: High before relying on Massive in demos.

**Configuration edge cases are not tested:**
- What's not tested: invalid `MARKET_POLL_INTERVAL_SECONDS`, invalid `MARKET_STALE_AFTER_SECONDS`, env-file path resolution, and future LLM env defaults.
- Files: `backend/app/core/config.py:8`, `backend/app/core/config.py:9`, `backend/app/market/service.py:43`, `backend/tests/test_api.py`
- Risk: Misconfiguration can produce startup failures or inconsistent provider selection across local, Docker, and CI runs.
- Priority: Medium.

**No coverage exists for planned portfolio, persistence, frontend, LLM, or E2E flows:**
- What's not tested: Trade execution, P&L math, database initialization, watchlist CRUD, chat structured-output parsing, AI guardrails, React rendering, Playwright startup, and reconnect flows.
- Files: `planning/PLAN.md:528`, `planning/PLAN.md:541`, `planning/PLAN.md:548`, `planning/PLAN.md:562`, `backend/tests/`
- Risk: These are missing because the code is not implemented. Future phases should add tests with each slice rather than carrying these as unverified acceptance criteria.
- Priority: High as each feature is introduced.

---

*Concerns audit: 2026-07-31*
