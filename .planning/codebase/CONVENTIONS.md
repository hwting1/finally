# Coding Conventions

**Analysis Date:** 2026-07-31

## Naming Patterns

**Files:**
- Use lowercase `snake_case.py` for modules in `backend/app`, such as `backend/app/market/serialization.py`, `backend/app/market/validation.py`, and `backend/app/core/config.py`.
- Use `test_*.py` for test modules in `backend/tests`, such as `backend/tests/test_simulator.py`, `backend/tests/test_api.py`, `backend/tests/test_massive.py`, and `backend/tests/test_cache_service_provider.py`.
- Keep package marker files as `__init__.py` in each package directory, such as `backend/app/__init__.py`, `backend/app/api/__init__.py`, and `backend/app/market/__init__.py`.
- Keep backend-only runnable scripts at the backend root, as in `backend/market_data_demo.py`.

**Functions:**
- Use `snake_case` for functions and methods, such as `create_app` in `backend/app/main.py`, `normalize_ticker_set` in `backend/app/market/validation.py`, `choose_snapshot_price` in `backend/app/market/massive.py`, and `build_dashboard` in `backend/market_data_demo.py`.
- Use leading underscores for private module helpers and private methods, such as `_positive_float`, `_mark_http_error`, and `_mark_unhealthy` in `backend/app/market/massive.py`, plus `_run_loop` in `backend/app/market/service.py`.
- Use verb phrases for async operations, such as `get_prices`, `get_previous_day_bars`, `refresh_once`, `refresh_tracked_tickers`, and `add_tracked_ticker` in `backend/app/market/provider.py` and `backend/app/market/service.py`.
- Use route handler names that describe returned resources, such as `get_prices`, `get_price`, and `market_health` in `backend/app/api/market.py`, plus `stream_prices` in `backend/app/api/stream.py`.

**Variables:**
- Use `snake_case` for locals and attributes, such as `market_move`, `previous_close`, `fallback_timestamp`, `poll_interval_seconds`, and `stale_after_seconds` in `backend/app/market/simulator.py`, `backend/app/market/massive.py`, and `backend/app/market/service.py`.
- Use uppercase constants for module-level fixed values, such as `BASE_URL` in `backend/app/market/massive.py`, `DEFAULT_WATCHLIST_TICKERS` in `backend/app/market/service.py`, and `RUN_SECONDS` in `backend/market_data_demo.py`.
- Use leading underscores for private instance state, such as `_quotes` and `_lock` in `backend/app/market/cache.py`, `_task` and `_stop` in `backend/app/market/service.py`, and `_health` in `backend/app/market/massive.py`.
- Use `ticker` for a single normalized symbol and `tickers` or `symbols` for collections in `backend/app/market/provider.py`, `backend/app/market/validation.py`, and `backend/app/market/massive.py`.

**Types:**
- Use `PascalCase` for classes, dataclasses, protocols, and enums, such as `Settings` in `backend/app/core/config.py`, `PriceQuote` and `MarketProviderHealth` in `backend/app/market/models.py`, `MarketDataProvider` in `backend/app/market/provider.py`, and `SimulatedMarketDataProvider` in `backend/app/market/simulator.py`.
- Use `StrEnum` for string-valued domain enums in `backend/app/market/models.py`.
- Use `@dataclass(frozen=True, slots=True)` for immutable value objects in `backend/app/market/models.py`; use `@dataclass(slots=True)` for mutable internal simulation state in `backend/app/market/simulator.py`.
- Use `Protocol` for service contracts, as in `MarketDataProvider` and `MarketSettings` in `backend/app/market/provider.py`.

## Code Style

**Formatting:**
- Tool used: Ruff configuration is declared in `backend/pyproject.toml`; no standalone `.prettierrc`, `.eslintrc`, `ruff.toml`, `pytest.ini`, or `.coveragerc` is present.
- Key settings: `backend/pyproject.toml` sets `[tool.ruff] line-length = 100` and `target-version = "py311"`.
- Use `from __future__ import annotations` in application modules, as shown in `backend/app/main.py`, `backend/app/market/models.py`, `backend/app/market/cache.py`, `backend/app/market/service.py`, `backend/app/market/provider.py`, `backend/app/market/simulator.py`, `backend/app/market/massive.py`, and `backend/market_data_demo.py`.
- Keep imports and code within the 100-character Ruff line target from `backend/pyproject.toml`; wrap multi-argument calls like `MarketDataService(...)` in `backend/app/main.py` and `httpx.AsyncClient(...)` in `backend/app/market/massive.py`.

**Linting:**
- Tool used: Ruff configuration only, in `backend/pyproject.toml`.
- Key rules: only `line-length` and `target-version` are configured in `backend/pyproject.toml`; no select/ignore rule set is declared.
- Ruff is configured but not listed in `[dependency-groups].dev` in `backend/pyproject.toml`; the declared dev dependency is `pytest>=8.0`.
- Use `uv run python -m compileall app tests market_data_demo.py` from `backend/` as the documented syntax check in `backend/README.md` and `backend/AGENTS.md`.

## Import Organization

**Order:**
1. Future imports first: `from __future__ import annotations` appears before all other imports in application modules such as `backend/app/market/service.py`.
2. Standard library imports next: examples include `asyncio`, `contextlib`, `dataclasses`, `datetime`, `random`, and `typing` in `backend/app/market/service.py`, `backend/app/market/simulator.py`, and `backend/app/market/massive.py`.
3. Third-party imports next: examples include `fastapi` in `backend/app/api/market.py`, `fastapi.responses` in `backend/app/api/stream.py`, `httpx` in `backend/app/market/massive.py`, `pydantic_settings` in `backend/app/core/config.py`, and `rich` in `backend/market_data_demo.py`.
4. Local application imports last: examples include `from app.market.models import PriceQuote` in `backend/app/market/cache.py` and `from app.market.provider import create_market_provider` in `backend/app/main.py`.

**Path Aliases:**
- Use absolute package imports rooted at `app`, enabled by `pythonpath = ["."]` in `backend/pyproject.toml`.
- Do not use relative imports inside `backend/app`; use `from app.market...` as in `backend/app/api/market.py`, `backend/app/market/cache.py`, `backend/app/market/service.py`, and `backend/app/market/provider.py`.
- Tests in `backend/tests` import production modules through the same `app` package root, as shown in `backend/tests/test_api.py`, `backend/tests/test_massive.py`, and `backend/tests/test_cache_service_provider.py`.

## Error Handling

**Patterns:**
- Raise `ValueError` for invalid construction arguments, as in `MarketDataService.__init__` in `backend/app/market/service.py` and `SimulatedMarketDataProvider.__init__` in `backend/app/market/simulator.py`.
- Raise `HTTPException` with JSON-object `detail` codes from FastAPI routes, as in `backend/app/api/market.py`:

```python
raise HTTPException(status_code=400, detail={"code": "INVALID_TICKER"})
raise HTTPException(status_code=404, detail={"code": "MARKET_DATA_UNAVAILABLE"})
```

- Convert provider/network failures into degraded provider health rather than raising through the service boundary, as in `MassiveMarketDataProvider.get_prices` and `_mark_unhealthy` in `backend/app/market/massive.py`.
- Return empty dictionaries for unavailable provider data from provider methods, as in `get_prices` and `get_previous_day_bars` in `backend/app/market/massive.py`, and for empty ticker input in `backend/app/market/simulator.py`.
- Suppress `asyncio.CancelledError` during service shutdown in `backend/app/market/service.py`.
- Background refresh errors are swallowed in `_run_loop` in `backend/app/market/service.py`; callers observe provider health/cache state rather than exceptions.

## Logging

**Framework:** console/Rich for the terminal demo; no application logger is configured.

**Patterns:**
- API and market service modules such as `backend/app/main.py`, `backend/app/api/market.py`, `backend/app/api/stream.py`, `backend/app/market/service.py`, and `backend/app/market/massive.py` do not call `logging` or `print`.
- Use `MarketProviderHealth` from `backend/app/market/models.py` as the observable provider status object instead of log-only status.
- Use `rich.console.Console.print` only in the interactive demo script `backend/market_data_demo.py`.

## Comments

**When to Comment:**
- Prefer module docstrings for every non-empty application module, such as `backend/app/main.py`, `backend/app/market/models.py`, `backend/app/market/cache.py`, `backend/app/market/provider.py`, `backend/app/market/simulator.py`, and `backend/app/market/massive.py`.
- Use class docstrings for public domain classes and providers, such as `PriceQuote`, `DailyBar`, and `MarketProviderHealth` in `backend/app/market/models.py`, plus `SimulatedMarketDataProvider` in `backend/app/market/simulator.py`.
- Keep inline comments sparse; business rules are represented through function names, constants, tests, and docstrings in `backend/app/market`.

**JSDoc/TSDoc:**
- Not applicable; no TypeScript source is present in the mapped implementation.
- Python docstrings are the documented convention in `backend/app/market/models.py`, `backend/app/market/provider.py`, and `backend/market_data_demo.py`.

## Function Design

**Size:** Keep functions focused around one service responsibility. Examples include `quote_to_payload` in `backend/app/market/serialization.py`, `normalize_ticker_set` in `backend/app/market/validation.py`, `_positive_float` in `backend/app/market/massive.py`, and `refresh_once` in `backend/app/market/service.py`.

**Parameters:** Use explicit typed parameters and keyword-only options for optional construction controls, as in `MassiveMarketDataProvider.__init__` in `backend/app/market/massive.py` and `SimulatedMarketDataProvider.__init__` in `backend/app/market/simulator.py`.

**Return Values:** Use precise Python 3.11 union syntax and generic containers, such as `PriceQuote | None`, `dict[str, PriceQuote]`, `set[str]`, `MarketProviderHealth`, and `StreamingResponse` in `backend/app/market/massive.py`, `backend/app/market/cache.py`, `backend/app/market/service.py`, and `backend/app/api/stream.py`.

## Module Design

**Exports:** Modules export concrete classes/functions directly; no barrel exports are defined in `backend/app/market/__init__.py`, `backend/app/api/__init__.py`, or `backend/app/__init__.py`.

**Barrel Files:** Barrel files are not used. Import concrete modules directly, as in `backend/app/main.py` importing `app.api.market`, `app.api.stream`, `PriceCache`, `create_market_provider`, and `MarketDataService`.

**Dependency Injection:** Inject provider, cache, ticker loader, transport, and settings instead of hard-coding external state. Examples are `create_app(app_settings: Settings = settings)` in `backend/app/main.py`, `MarketDataService(provider, cache, ticker_loader, poll_interval_seconds)` in `backend/app/market/service.py`, and `MassiveMarketDataProvider(..., transport=...)` in `backend/app/market/massive.py`.

**State Ownership:** Keep shared mutable market state behind explicit service/cache objects. `PriceCache` owns `_quotes` in `backend/app/market/cache.py`; `MarketDataService` owns tracked tickers and lifecycle in `backend/app/market/service.py`; FastAPI stores these objects on `app.state` in `backend/app/main.py`.

---

*Convention analysis: 2026-07-31*
