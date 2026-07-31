from fastapi.testclient import TestClient
from pathlib import Path

from app.core.config import Settings
from app.main import create_app


def make_test_app(tmp_path: Path):
    return create_app(
        Settings(
            database_path=str(tmp_path / "finally-test.db"),
            massive_api_key="",
            market_poll_interval_seconds=0.5,
            market_stale_after_seconds=30.0,
            market_simulator_seed=42,
        )
    )


def test_health_endpoint(tmp_path: Path) -> None:
    with TestClient(make_test_app(tmp_path)) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "market": "simulator", "chat_enabled": False}


def test_market_prices_endpoint_returns_seeded_snapshot(tmp_path: Path) -> None:
    with TestClient(make_test_app(tmp_path)) as client:
        response = client.get("/api/market/prices")

    assert response.status_code == 200
    payload = response.json()
    assert "prices" in payload
    tickers = {quote["ticker"] for quote in payload["prices"]}
    assert {"AAPL", "MSFT", "JPM", "V"} <= tickers
    assert all(quote["source"] == "simulator" for quote in payload["prices"])


def test_market_price_endpoint_validates_and_loads_ticker(tmp_path: Path) -> None:
    with TestClient(make_test_app(tmp_path)) as client:
        invalid = client.get("/api/market/prices/TOOLONG")
        valid = client.get("/api/market/prices/amd")

    assert invalid.status_code == 400
    assert valid.status_code == 200
    assert valid.json()["price"]["ticker"] == "AMD"


def test_market_health_endpoint(tmp_path: Path) -> None:
    with TestClient(make_test_app(tmp_path)) as client:
        response = client.get("/api/market/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["market"]["source"] == "simulator"
    assert payload["market"]["ok"] is True


def test_watchlist_endpoint_returns_prices_and_supports_crud(tmp_path: Path) -> None:
    with TestClient(make_test_app(tmp_path)) as client:
        initial = client.get("/api/watchlist")
        added = client.post("/api/watchlist", json={"ticker": "amd"})
        after_add = client.get("/api/watchlist")
        removed = client.delete("/api/watchlist/AMD")

    assert initial.status_code == 200
    initial_payload = initial.json()
    assert {"AAPL", "MSFT", "JPM", "V"} <= set(initial_payload["tickers"])
    assert all("ticker" in item and "price" in item for item in initial_payload["items"])

    assert added.status_code == 200
    assert added.json()["ticker"] == "AMD"
    assert added.json()["added"] is True
    assert "AMD" in after_add.json()["tickers"]

    assert removed.status_code == 200
    assert removed.json() == {"ticker": "AMD", "removed": True}


def test_watchlist_invalid_ticker_returns_structured_error(tmp_path: Path) -> None:
    with TestClient(make_test_app(tmp_path)) as client:
        response = client.post("/api/watchlist", json={"ticker": "TOOLONG"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_TICKER"


def test_portfolio_trade_buy_sell_and_history(tmp_path: Path) -> None:
    with TestClient(make_test_app(tmp_path)) as client:
        initial = client.get("/api/portfolio")
        buy = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "side": "buy", "quantity": 2},
        )
        portfolio = client.get("/api/portfolio")
        history = client.get("/api/portfolio/history", params={"limit": 10})
        sell = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "side": "sell", "quantity": 1.5},
        )

    assert initial.status_code == 200
    assert initial.json()["cash_balance"] == 10_000
    assert initial.json()["positions"] == []

    assert buy.status_code == 200
    buy_payload = buy.json()
    assert buy_payload["trade"]["ticker"] == "AAPL"
    assert buy_payload["trade"]["side"] == "buy"
    assert buy_payload["position"]["quantity"] == 2
    assert buy_payload["cash_balance"] < 10_000

    assert portfolio.status_code == 200
    assert portfolio.json()["positions"][0]["ticker"] == "AAPL"

    assert history.status_code == 200
    assert history.json()["limit"] == 10
    assert len(history.json()["history"]) >= 2

    assert sell.status_code == 200
    assert sell.json()["position"]["quantity"] == 0.5


def test_trade_validation_uses_structured_errors(tmp_path: Path) -> None:
    with TestClient(make_test_app(tmp_path)) as client:
        invalid_ticker = client.post(
            "/api/portfolio/trade",
            json={"ticker": "TOOLONG", "side": "buy", "quantity": 1},
        )
        invalid_side = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "side": "hold", "quantity": 1},
        )
        insufficient_shares = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "side": "sell", "quantity": 1},
        )

    assert invalid_ticker.status_code == 400
    assert invalid_ticker.json()["error"]["code"] == "INVALID_TICKER"
    assert invalid_side.status_code == 400
    assert invalid_side.json()["error"]["code"] == "INVALID_TRADE_SIDE"
    assert insufficient_shares.status_code == 400
    assert insufficient_shares.json()["error"]["code"] == "INSUFFICIENT_SHARES"


def test_chat_endpoint_mock_mode_uses_backend_adapters(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            database_path=str(tmp_path / "finally-test.db"),
            llm_mock=True,
            massive_api_key="",
            market_poll_interval_seconds=0.5,
            market_simulator_seed=42,
        )
    )

    with TestClient(app) as client:
        response = client.post("/api/chat", json={"message": "buy 1 AAPL"})
        portfolio = client.get("/api/portfolio")

    assert response.status_code == 200
    payload = response.json()
    assert payload["chat_enabled"] is True
    assert payload["actions"][0]["status"] == "executed"
    assert portfolio.json()["positions"][0]["ticker"] == "AAPL"


def test_stream_prices_endpoint_is_registered(tmp_path: Path) -> None:
    with TestClient(make_test_app(tmp_path)) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/api/stream/prices" in response.json()["paths"]
