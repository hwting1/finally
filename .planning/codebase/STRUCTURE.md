# Codebase Structure

**Analysis Date:** 2026-07-31

## Directory Layout

```text
finally/
├── AGENTS.md                 # Project-level agent instructions pointing to `planning/PLAN.md`
├── CLAUDE.md                 # Claude compatibility marker/instructions
├── LICENSE                   # Project license
├── README.md                 # Repository overview and backend run commands
├── backend/                  # Python uv/FastAPI backend project
│   ├── AGENTS.md             # Backend-specific agent instructions and market data rules
│   ├── CLAUDE.md             # Claude compatibility marker/instructions
│   ├── README.md             # Backend usage, endpoints, architecture summary
│   ├── app/                  # Importable FastAPI application package
│   │   ├── __init__.py       # App package marker
│   │   ├── main.py           # FastAPI app factory, lifespan, route registration
│   │   ├── api/              # HTTP and SSE route modules
│   │   ├── core/             # Runtime settings
│   │   └── market/           # Market domain, providers, cache, service, serialization
│   ├── market_data_demo.py   # Rich terminal simulator demo
│   ├── pyproject.toml        # Backend dependencies, pytest config, Ruff settings
│   ├── tests/                # Backend pytest suite
│   └── uv.lock               # Locked backend dependency graph
├── fronted/                  # Empty frontend placeholder directory
├── planning/                 # Product and market-data planning documents
│   ├── PLAN.md               # Main product specification
│   ├── MARKET_DATA_SUMMARY.md # Implemented market-data summary
│   └── archive/              # Archived market-data design/review notes
└── .planning/
    └── codebase/             # Generated GSD codebase maps
        ├── ARCHITECTURE.md   # Architecture map
        └── STRUCTURE.md      # Structure map
```

## Directory Purposes

**Repository Root (`.`):**
- Purpose: Project coordination, top-level docs, Git metadata, agent config, and high-level entrypoints.
- Contains: `README.md`, `AGENTS.md`, `CLAUDE.md`, `LICENSE`, `.gitignore`, `.codex/`, `.claude/`, `.github/`, `.planning/`, `backend/`, `fronted/`, `planning/`.
- Key files: `README.md`, `AGENTS.md`, `planning/PLAN.md`.

**Backend Project (`backend/`):**
- Purpose: Self-contained Python `uv` project for the implemented FastAPI market-data backend.
- Contains: Backend package `backend/app/`, tests `backend/tests/`, demo script `backend/market_data_demo.py`, package config `backend/pyproject.toml`, lockfile `backend/uv.lock`.
- Key files: `backend/README.md`, `backend/AGENTS.md`, `backend/pyproject.toml`, `backend/app/main.py`.

**Application Package (`backend/app/`):**
- Purpose: Importable backend application code.
- Contains: App factory `backend/app/main.py`, API routers in `backend/app/api/`, settings in `backend/app/core/`, market data modules in `backend/app/market/`.
- Key files: `backend/app/main.py`, `backend/app/__init__.py`.

**API Routes (`backend/app/api/`):**
- Purpose: FastAPI route adapters for REST market diagnostics and SSE streaming.
- Contains: `backend/app/api/market.py`, `backend/app/api/stream.py`, `backend/app/api/__init__.py`.
- Key files: `backend/app/api/market.py`, `backend/app/api/stream.py`.

**Core Settings (`backend/app/core/`):**
- Purpose: Environment-backed backend settings.
- Contains: `backend/app/core/config.py`, `backend/app/core/__init__.py`.
- Key files: `backend/app/core/config.py`.

**Market Package (`backend/app/market/`):**
- Purpose: Provider-independent market domain, provider selection, simulator, Massive REST client, cache, service loop, serialization, and validation.
- Contains: `backend/app/market/models.py`, `backend/app/market/provider.py`, `backend/app/market/simulator.py`, `backend/app/market/massive.py`, `backend/app/market/cache.py`, `backend/app/market/service.py`, `backend/app/market/serialization.py`, `backend/app/market/validation.py`, `backend/app/market/__init__.py`.
- Key files: `backend/app/market/service.py`, `backend/app/market/cache.py`, `backend/app/market/provider.py`, `backend/app/market/models.py`.

**Backend Tests (`backend/tests/`):**
- Purpose: Pytest coverage for the FastAPI API, market cache/service/provider factory, simulator, and Massive mapping.
- Contains: `backend/tests/test_api.py`, `backend/tests/test_cache_service_provider.py`, `backend/tests/test_simulator.py`, `backend/tests/test_massive.py`.
- Key files: `backend/tests/test_api.py`, `backend/tests/test_cache_service_provider.py`, `backend/tests/test_simulator.py`, `backend/tests/test_massive.py`.

**Frontend Placeholder (`fronted/`):**
- Purpose: Empty placeholder directory using the repository's existing spelling.
- Contains: No source files.
- Key files: Not detected.

**Planning Docs (`planning/`):**
- Purpose: Product specification and market-data design/reference documents for agents.
- Contains: `planning/PLAN.md`, `planning/MARKET_DATA_SUMMARY.md`, archived design notes in `planning/archive/`.
- Key files: `planning/PLAN.md`, `planning/MARKET_DATA_SUMMARY.md`.

**GSD Codebase Maps (`.planning/codebase/`):**
- Purpose: Generated architecture and structure reference documents consumed by GSD planning/execution workflows.
- Contains: `ARCHITECTURE.md`, `STRUCTURE.md`.
- Key files: `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`.

## Key File Locations

**Entry Points:**
- `backend/app/main.py`: FastAPI app factory, lifespan-managed service wiring, router registration, `/api/health`, module-level ASGI `app`.
- `backend/market_data_demo.py`: Rich terminal simulator demo entry point.
- `backend/tests/test_api.py`: Test app factory usage via `create_app(Settings(...))`.

**Configuration:**
- `backend/pyproject.toml`: Python dependencies, pytest `pythonpath`, pytest `-q` option, Ruff line length and target version.
- `backend/uv.lock`: Locked dependency versions for the backend `uv` project.
- `backend/app/core/config.py`: `Settings` with `MASSIVE_API_KEY`, market poll interval, stale threshold, and simulator seed.
- `.gitignore`: Ignore rules for local/generated files.
- `.env`: Present at repository root; contains local environment configuration and must not be read or quoted.

**Core Logic:**
- `backend/app/market/service.py`: Background refresh loop and tracked ticker set.
- `backend/app/market/cache.py`: In-memory latest-price cache.
- `backend/app/market/provider.py`: Provider protocol and simulator/Massive factory.
- `backend/app/market/models.py`: Provider-independent market models.
- `backend/app/market/simulator.py`: Deterministic simulator provider.
- `backend/app/market/massive.py`: Massive REST provider.
- `backend/app/market/serialization.py`: JSON payload formatting.
- `backend/app/market/validation.py`: Ticker normalization and validation.

**API Surface:**
- `backend/app/api/market.py`: `GET /api/market/prices`, `GET /api/market/prices/{ticker}`, `GET /api/market/health`.
- `backend/app/api/stream.py`: `GET /api/stream/prices`.
- `backend/app/main.py`: `GET /api/health`.

**Testing:**
- `backend/tests/test_api.py`: FastAPI route smoke and behavior tests.
- `backend/tests/test_cache_service_provider.py`: Cache, service, and provider factory tests.
- `backend/tests/test_simulator.py`: Simulator determinism and quote/bar behavior tests.
- `backend/tests/test_massive.py`: Massive snapshot and previous-day bar mapping tests.

**Documentation:**
- `README.md`: Repository overview, validation notes, run commands, endpoint list.
- `backend/README.md`: Backend usage, architecture module list, market data rules.
- `backend/AGENTS.md`: Backend-specific implementation rules.
- `planning/PLAN.md`: Product specification and intended architecture.
- `planning/MARKET_DATA_SUMMARY.md`: Market-data slice summary.

## Naming Conventions

**Files:**
- Python modules use lowercase snake_case: `backend/app/market/service.py`, `backend/app/market/serialization.py`, `backend/market_data_demo.py`.
- Test files use `test_*.py`: `backend/tests/test_api.py`, `backend/tests/test_massive.py`.
- Package markers are named `__init__.py`: `backend/app/__init__.py`, `backend/app/market/__init__.py`.
- Markdown docs use uppercase names for agent-facing instructions and plans: `AGENTS.md`, `README.md`, `planning/PLAN.md`, `.planning/codebase/ARCHITECTURE.md`.

**Directories:**
- Backend package directories use short lowercase names: `backend/app/api/`, `backend/app/core/`, `backend/app/market/`.
- Tests live in a sibling `tests` directory under the backend project: `backend/tests/`.
- Planning docs live under `planning/`; generated GSD maps live under `.planning/codebase/`.
- Preserve the existing frontend placeholder spelling `fronted/` when adding files under that subtree.

**Symbols:**
- Classes use PascalCase: `Settings`, `PriceCache`, `MarketDataService`, `SimulatedMarketDataProvider`, `MassiveMarketDataProvider`.
- Functions and methods use snake_case: `create_app`, `get_prices`, `stream_prices`, `create_market_provider`, `default_poll_interval_seconds`.
- Constants use uppercase snake case: `DEFAULT_WATCHLIST_TICKERS`, `DEFAULT_SEED_PRICES`, `BASE_URL`.
- Enum values use lowercase string values through `StrEnum`: `MarketSource.SIMULATOR` maps to `"simulator"`, `MarketSession.OPEN` maps to `"open"`.

## Where to Add New Code

**New REST Endpoint:**
- Primary code: Add a route module or route function under `backend/app/api/`.
- Wiring: Include a new router in `backend/app/main.py`.
- Service dependencies: Read shared market data through `request.app.state.market_service` or a service composed in `backend/app/main.py`.
- Tests: Add route tests under `backend/tests/test_api.py` or a new `backend/tests/test_<feature>.py`.

**New SSE/Event Stream:**
- Primary code: Add stream logic under `backend/app/api/stream.py` or a new route module under `backend/app/api/`.
- Serialization: Put reusable payload conversion in `backend/app/market/serialization.py` or a feature-specific serialization helper.
- Tests: Add API-level tests under `backend/tests/`.

**New Market Data Provider:**
- Implementation: Add `backend/app/market/<provider_name>.py`.
- Contract: Implement `MarketDataProvider` from `backend/app/market/provider.py`.
- Models: Return `PriceQuote`, `DailyBar`, and `MarketProviderHealth` from `backend/app/market/models.py`.
- Factory: Extend `create_market_provider()` in `backend/app/market/provider.py`.
- Tests: Add provider tests under `backend/tests/test_<provider_name>.py`.

**New Market Domain Model:**
- Implementation: Add provider-independent dataclasses/enums to `backend/app/market/models.py`.
- Serialization: Add JSON conversion in `backend/app/market/serialization.py`.
- Tests: Add unit tests under `backend/tests/test_<domain_area>.py`.

**New Market Service Behavior:**
- Primary code: Extend `backend/app/market/service.py` when the behavior coordinates providers, tracked tickers, or cache updates.
- Cache behavior: Extend `backend/app/market/cache.py` when the behavior changes current-price storage or stale semantics.
- Tests: Extend `backend/tests/test_cache_service_provider.py`.

**New Configuration:**
- Primary code: Add fields to `Settings` in `backend/app/core/config.py`.
- Composition: Consume the setting from `backend/app/main.py` or provider/service factory code.
- Documentation: Update `backend/README.md` and `README.md` when commands or environment behavior changes.

**New Terminal Demo Feature:**
- Primary code: Extend `backend/market_data_demo.py`.
- Shared logic: Move reusable market logic into `backend/app/market/` before using it from both the demo and API.
- Tests: Add pure function tests under `backend/tests/` when demo helpers become non-trivial.

**New Frontend Code:**
- Implementation: Use the existing `fronted/` directory name.
- API calls: Target backend endpoints in `backend/app/api/market.py` and `backend/app/api/stream.py`.
- Shared backend contract: Preserve object-shaped JSON payloads from `backend/app/market/serialization.py`.

**Utilities:**
- Shared market helpers: `backend/app/market/`.
- App-wide backend helpers: `backend/app/core/`.
- Route-only helpers: Keep local to `backend/app/api/<route_module>.py` until reused.

## Special Directories

**`.codex/`:**
- Purpose: Codex/GSD local configuration, agents, hooks, core workflow files, and local project skills.
- Generated: Yes.
- Committed: Yes.

**`.claude/`:**
- Purpose: Claude/GSD compatibility configuration, agents, hooks, and core workflow files.
- Generated: Yes.
- Committed: Yes.

**`.github/`:**
- Purpose: GitHub-oriented agent/config files.
- Generated: No.
- Committed: Yes.

**`.planning/codebase/`:**
- Purpose: Generated codebase intelligence documents.
- Generated: Yes.
- Committed: Yes.

**`backend/.venv/`:**
- Purpose: Local Python virtual environment for the backend.
- Generated: Yes.
- Committed: No.

**`planning/archive/`:**
- Purpose: Archived market-data design and review documents.
- Generated: No.
- Committed: Yes.

**`fronted/`:**
- Purpose: Placeholder for frontend implementation using the repository's existing spelling.
- Generated: No.
- Committed: Yes.

---

*Structure analysis: 2026-07-31*
