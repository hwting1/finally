# Technology Stack

**Analysis Date:** 2026-07-31

## Languages

**Primary:**
- Python >=3.11 - Backend application, market data providers, tests, and terminal demo in `backend/app/`, `backend/tests/`, and `backend/market_data_demo.py`.

**Secondary:**
- Markdown - Product and implementation documentation in `README.md`, `backend/README.md`, `planning/PLAN.md`, and `planning/MARKET_DATA_SUMMARY.md`.
- TOML - Python project, dependency, pytest, and Ruff configuration in `backend/pyproject.toml`.

## Runtime

**Environment:**
- Python >=3.11 - Required by `backend/pyproject.toml` and documented in `backend/README.md`.
- ASGI runtime through Uvicorn - Local startup command is `uv run uvicorn app.main:app --reload` from `backend/README.md`.

**Package Manager:**
- uv - The backend is a uv-managed Python project in `backend/pyproject.toml`.
- Lockfile: present at `backend/uv.lock`.

## Frameworks

**Core:**
- FastAPI >=0.115.0, resolved 0.141.1 - API application factory, lifespan startup, and route registration in `backend/app/main.py`.
- Starlette resolved 1.3.1 - FastAPI runtime dependency in `backend/uv.lock`, used indirectly by `backend/app/main.py` and `backend/app/api/stream.py`.
- Pydantic Settings >=2.0.0, resolved 2.14.2 - Environment-backed settings in `backend/app/core/config.py`.
- Pydantic resolved 2.13.4 - Transitive runtime model/validation dependency in `backend/uv.lock`.

**Testing:**
- pytest >=8.0, resolved 9.1.1 - Test runner configured in `backend/pyproject.toml`; tests live in `backend/tests/`.
- FastAPI TestClient - API test client used in `backend/tests/test_api.py`.
- httpx MockTransport - Massive provider HTTP mocking used in `backend/tests/test_massive.py`.

**Build/Dev:**
- uvicorn >=0.30.0, resolved 0.52.0 - ASGI server for `backend/app/main.py`.
- Ruff - Line length and target version configured in `[tool.ruff]` in `backend/pyproject.toml`; no separate `ruff.toml` detected.
- Rich >=13.9.0, resolved 15.0.0 - Terminal market data demo UI in `backend/market_data_demo.py`.

## Key Dependencies

**Critical:**
- `fastapi` >=0.115.0 / resolved 0.141.1 - Owns HTTP route surface in `backend/app/main.py`, `backend/app/api/market.py`, and `backend/app/api/stream.py`.
- `httpx` >=0.27.0 / resolved 0.28.1 - Direct Massive REST client in `backend/app/market/massive.py`; also used for `httpx.MockTransport` tests in `backend/tests/test_massive.py`.
- `pydantic-settings` >=2.0.0 / resolved 2.14.2 - Reads `.env` and `../.env` for `Settings` in `backend/app/core/config.py`.
- `uvicorn` >=0.30.0 / resolved 0.52.0 - Serves the FastAPI app declared as `app = create_app()` in `backend/app/main.py`.

**Infrastructure:**
- `httpx2` >=0.28.0 / resolved 2.9.1 - Declared in `backend/pyproject.toml` and locked in `backend/uv.lock`; no current imports detected under `backend/app/` or `backend/tests/`.
- `rich` >=13.9.0 / resolved 15.0.0 - CLI/demo rendering dependency for `backend/market_data_demo.py`.
- `anyio` resolved 4.14.2 - Async runtime dependency of FastAPI/httpx in `backend/uv.lock`.
- `pytest` >=8.0 / resolved 9.1.1 - Developer dependency group in `backend/pyproject.toml`.

## Configuration

**Environment:**
- Runtime settings are centralized in `backend/app/core/config.py` using `SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")`.
- `.env` exists at repo root as `.env` and is ignored by `.gitignore`; contents were not read.
- `MASSIVE_API_KEY` in `backend/app/core/config.py` selects provider mode: empty string selects `SimulatedMarketDataProvider`, non-empty selects `MassiveMarketDataProvider` via `backend/app/market/provider.py`.
- `MARKET_POLL_INTERVAL_SECONDS` in `backend/app/core/config.py` overrides default polling cadence used by `backend/app/market/provider.py`.
- `MARKET_STALE_AFTER_SECONDS` in `backend/app/core/config.py` controls staleness marking in `backend/app/market/cache.py` and Massive quote freshness in `backend/app/market/massive.py`.
- `MARKET_SIMULATOR_SEED` in `backend/app/core/config.py` controls deterministic simulator output in `backend/app/market/simulator.py`.
- Planned LLM settings appear in `planning/PLAN.md`, but `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_MOCK` are not implemented in `backend/app/core/config.py`.

**Build:**
- `backend/pyproject.toml` defines project metadata, dependencies, pytest configuration, and Ruff configuration.
- `backend/uv.lock` pins resolved dependency versions for reproducible uv installs.
- No root `package.json`, `requirements.txt`, `Dockerfile`, `docker-compose.yml`, `tsconfig.json`, `.nvmrc`, or `.python-version` detected in the current repo root.
- No committed `.env.example` detected, although `planning/PLAN.md` describes one as planned.

## Platform Requirements

**Development:**
- Use Python >=3.11 and uv from the `backend/` directory.
- Run all backend tests with `cd backend` then `uv run pytest`, as documented in `backend/README.md`.
- Run the API with `cd backend` then `uv run uvicorn app.main:app --reload`, as documented in `README.md`.
- Run the terminal demo with `cd backend` then `uv run python market_data_demo.py`, as documented in `backend/README.md`.

**Production:**
- Current implementation exposes an ASGI FastAPI app in `backend/app/main.py`; deploy with an ASGI server such as Uvicorn.
- No production Dockerfile, docker-compose file, CI workflow, deployment config, or frontend static export is present in the current file set.
- `planning/PLAN.md` describes future container/static-frontend deployment, but current state is backend-only.

---

*Stack analysis: 2026-07-31*
