from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def make_test_app():
    return create_app(
        Settings(
            massive_api_key="",
            market_poll_interval_seconds=0.5,
            market_stale_after_seconds=30.0,
            market_simulator_seed=42,
        )
    )


def test_health_endpoint() -> None:
    with TestClient(make_test_app()) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_market_prices_endpoint_returns_seeded_snapshot() -> None:
    with TestClient(make_test_app()) as client:
        response = client.get("/api/market/prices")

    assert response.status_code == 200
    payload = response.json()
    assert "prices" in payload
    tickers = {quote["ticker"] for quote in payload["prices"]}
    assert {"AAPL", "MSFT", "JPM", "V"} <= tickers
    assert all(quote["source"] == "simulator" for quote in payload["prices"])


def test_market_price_endpoint_validates_and_loads_ticker() -> None:
    with TestClient(make_test_app()) as client:
        invalid = client.get("/api/market/prices/TOOLONG")
        valid = client.get("/api/market/prices/amd")

    assert invalid.status_code == 400
    assert valid.status_code == 200
    assert valid.json()["price"]["ticker"] == "AMD"


def test_market_health_endpoint() -> None:
    with TestClient(make_test_app()) as client:
        response = client.get("/api/market/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["market"]["source"] == "simulator"
    assert payload["market"]["ok"] is True
