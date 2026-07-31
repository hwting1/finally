# Testing Patterns

**Analysis Date:** 2026-07-31

## Test Framework

**Runner:**
- pytest `>=8.0`, declared in `[dependency-groups].dev` in `backend/pyproject.toml`.
- Config: `backend/pyproject.toml` contains `[tool.pytest.ini_options]`.
- Pytest addopts: `addopts = "-q"` in `backend/pyproject.toml`.
- Python import root: `pythonpath = ["."]` in `backend/pyproject.toml`.

**Assertion Library:**
- Use plain Python `assert` statements in `backend/tests/test_simulator.py`, `backend/tests/test_cache_service_provider.py`, `backend/tests/test_api.py`, and `backend/tests/test_massive.py`.
- Use `pytest.raises` for expected exceptions, as in `backend/tests/test_simulator.py`.

**Run Commands:**
```bash
cd backend
uv run pytest              # Run all tests
uv run pytest -q           # Quiet mode, also configured by backend/pyproject.toml
uv run python -m compileall app tests market_data_demo.py  # Syntax/import compile check
```

## Test File Organization

**Location:**
- Tests live in `backend/tests`, separate from implementation modules in `backend/app`.
- Test modules mirror behavior areas rather than one-to-one module names: `backend/tests/test_simulator.py` covers `backend/app/market/simulator.py`, `backend/tests/test_massive.py` covers `backend/app/market/massive.py`, `backend/tests/test_api.py` covers `backend/app/main.py` and `backend/app/api/market.py`, and `backend/tests/test_cache_service_provider.py` covers `backend/app/market/cache.py`, `backend/app/market/service.py`, and `backend/app/market/provider.py`.

**Naming:**
- Use `test_*.py` file names in `backend/tests`.
- Use `test_<behavior>() -> None` for test functions, such as `test_same_seed_and_ticker_sequence_is_deterministic` in `backend/tests/test_simulator.py`, `test_market_prices_endpoint_returns_seeded_snapshot` in `backend/tests/test_api.py`, and `test_massive_auth_failure_marks_unhealthy_without_quotes` in `backend/tests/test_massive.py`.
- Use local helper names like `run`, `provider`, `quote`, and `make_test_app` in `backend/tests/test_simulator.py`, `backend/tests/test_cache_service_provider.py`, and `backend/tests/test_api.py`.

**Structure:**
```text
backend/
+-- app/
|   +-- api/
|   +-- core/
|   +-- market/
+-- tests/
    +-- test_api.py
    +-- test_cache_service_provider.py
    +-- test_massive.py
    +-- test_simulator.py
```

## Test Structure

**Suite Organization:**
```python
# backend/tests/test_simulator.py
NOW = datetime(2026, 7, 30, 12, tzinfo=timezone.utc)
T = TypeVar("T")


def provider(seed: int = 42) -> SimulatedMarketDataProvider:
    return SimulatedMarketDataProvider(seed=seed, clock=lambda: NOW)


def run(awaitable: Awaitable[T]) -> T:
    return asyncio.run(awaitable)


def test_health_is_always_ok_and_tracks_success() -> None:
    simulator = provider()
    assert simulator.health().ok is True

    run(simulator.get_prices({"SPY"}))

    assert simulator.health().last_success_at == NOW
```

**Patterns:**
- Put deterministic constants at module scope, such as `NOW` in `backend/tests/test_simulator.py` and `backend/tests/test_cache_service_provider.py`.
- Build small local helpers rather than shared fixture files, such as `provider` and `run` in `backend/tests/test_simulator.py`, `quote` and `run` in `backend/tests/test_cache_service_provider.py`, and `make_test_app` in `backend/tests/test_api.py`.
- Use arrange/act/assert in one test function without comments, as shown across `backend/tests/test_massive.py`, `backend/tests/test_api.py`, and `backend/tests/test_cache_service_provider.py`.
- Use direct state assertions on returned dataclasses and JSON payloads, such as `quote.source is MarketSource.SIMULATOR` in `backend/tests/test_simulator.py` and `payload["market"]["ok"] is True` in `backend/tests/test_api.py`.

## Mocking

**Framework:** Local fake classes/functions and `httpx.MockTransport`; no `unittest.mock`, `pytest-mock`, or monkeypatch fixtures are used.

**Patterns:**
```python
# backend/tests/test_cache_service_provider.py
class RecordingProvider:
    def __init__(self) -> None:
        self.calls: list[set[str]] = []

    async def get_prices(self, tickers: set[str]) -> dict[str, PriceQuote]:
        self.calls.append(set(tickers))
        return {
            ticker: PriceQuote(
                ticker=ticker,
                price=100.0 + len(self.calls),
                previous_price=None,
                previous_close=100.0,
                timestamp=NOW,
                source=MarketSource.SIMULATOR,
                session=MarketSession.OPEN,
            )
            for ticker in tickers
        }
```

```python
# backend/tests/test_massive.py
def handler(request: httpx.Request) -> httpx.Response:
    assert request.headers["Authorization"].startswith("Bearer ")
    assert request.url.params["tickers"] == "AAPL,MSFT"
    return httpx.Response(200, json={"tickers": [...]})


provider = MassiveMarketDataProvider(
    "test-key",
    stale_after_seconds=999999999.0,
    transport=httpx.MockTransport(handler),
)
```

**What to Mock:**
- Mock external HTTP through the provider transport seam in `MassiveMarketDataProvider` from `backend/app/market/massive.py`; tests use `httpx.MockTransport` in `backend/tests/test_massive.py`.
- Mock provider contracts with small local fake classes when testing service/cache behavior, as with `RecordingProvider` in `backend/tests/test_cache_service_provider.py`.
- Mock clocks through constructor injection, as with `clock=lambda: NOW` for `SimulatedMarketDataProvider` in `backend/tests/test_simulator.py`.
- Mock app settings by constructing `Settings` directly in `backend/tests/test_api.py` and by defining a local dataclass `Settings` in `backend/tests/test_cache_service_provider.py`.

**What NOT to Mock:**
- Do not mock `PriceCache` when testing `MarketDataService`; `backend/tests/test_cache_service_provider.py` uses the real `PriceCache` from `backend/app/market/cache.py`.
- Do not call the real Massive API in tests; `backend/tests/test_massive.py` routes all HTTP through `httpx.MockTransport`.
- Do not require `.env` values in tests; `backend/tests/test_api.py` passes explicit `Settings` values to `create_app` from `backend/app/main.py`.
- Do not mock FastAPI routing for API tests; use `TestClient` from `fastapi.testclient` in `backend/tests/test_api.py`.

## Fixtures and Factories

**Test Data:**
```python
# backend/tests/test_cache_service_provider.py
def quote(ticker: str, price: float, timestamp: datetime = NOW) -> PriceQuote:
    return PriceQuote(
        ticker=ticker,
        price=price,
        previous_price=None,
        previous_close=100.0,
        timestamp=timestamp,
        source=MarketSource.SIMULATOR,
        session=MarketSession.OPEN,
    )
```

```python
# backend/tests/test_api.py
def make_test_app():
    return create_app(
        Settings(
            massive_api_key="",
            market_poll_interval_seconds=0.5,
            market_stale_after_seconds=30.0,
            market_simulator_seed=42,
        )
    )
```

**Location:**
- Test data helpers are local to the test files that use them: `provider` in `backend/tests/test_simulator.py`, `quote` and `RecordingProvider` in `backend/tests/test_cache_service_provider.py`, and `make_test_app` in `backend/tests/test_api.py`.
- There is no shared `backend/tests/conftest.py`, fixture package, or factory module.

## Coverage

**Requirements:** No coverage threshold is enforced. No `.coveragerc`, coverage command, or coverage dependency is detected in `backend/pyproject.toml`.

**View Coverage:**
```bash
Not configured
```

## Test Types

**Unit Tests:**
- Simulator unit tests in `backend/tests/test_simulator.py` cover deterministic seeded price generation, normalization, bounded movement, previous-day bars, weekend date handling, health tracking, and constructor validation for `backend/app/market/simulator.py`.
- Massive provider unit tests in `backend/tests/test_massive.py` cover snapshot price fallback, auth header/query construction, response mapping, auth failure health, and previous-day bar mapping for `backend/app/market/massive.py`.
- Cache/service/provider unit tests in `backend/tests/test_cache_service_provider.py` cover provider selection in `backend/app/market/provider.py`, previous-price/stale handling in `backend/app/market/cache.py`, and ticker tracking/refresh behavior in `backend/app/market/service.py`.

**Integration Tests:**
- API integration tests in `backend/tests/test_api.py` use `TestClient` against `create_app` in `backend/app/main.py` and exercise FastAPI lifespan setup plus routes in `backend/app/api/market.py`.
- The API tests validate `/api/health`, `/api/market/prices`, `/api/market/prices/{ticker}`, and `/api/market/health` in `backend/tests/test_api.py`.
- SSE route behavior in `backend/app/api/stream.py` is not directly exercised by the detected tests.

**E2E Tests:**
- Not used. No browser, Playwright, Selenium, or external API end-to-end test framework is detected.
- The terminal demo `backend/market_data_demo.py` is covered by the documented compile command in `backend/README.md`, not by behavioral tests in `backend/tests`.

## Common Patterns

**Async Testing:**
```python
# backend/tests/test_massive.py
def run(awaitable):
    return asyncio.run(awaitable)


def test_massive_auth_failure_marks_unhealthy_without_quotes() -> None:
    provider = MassiveMarketDataProvider(
        "bad-key",
        transport=httpx.MockTransport(lambda request: httpx.Response(403, json={})),
    )

    assert run(provider.get_prices({"AAPL"})) == {}
    assert provider.health().ok is False
```

**Error Testing:**
```python
# backend/tests/test_simulator.py
def test_update_interval_must_be_positive() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        SimulatedMarketDataProvider(update_interval_seconds=0)
```

```python
# backend/tests/test_api.py
def test_market_price_endpoint_validates_and_loads_ticker() -> None:
    with TestClient(make_test_app()) as client:
        invalid = client.get("/api/market/prices/TOOLONG")
        valid = client.get("/api/market/prices/amd")

    assert invalid.status_code == 400
    assert valid.status_code == 200
    assert valid.json()["price"]["ticker"] == "AMD"
```

---

*Testing analysis: 2026-07-31*
