import asyncio
from datetime import timezone

import httpx

from app.market.massive import MassiveMarketDataProvider, choose_snapshot_price
from app.market.models import MarketSource


def run(awaitable):
    return asyncio.run(awaitable)


def test_choose_snapshot_price_fallback_order() -> None:
    price, timestamp, stale = choose_snapshot_price(
        {
            "lastTrade": {"p": 10.0, "t": 1_700_000_000_000_000_000},
            "lastQuote": {"p": 9.0, "P": 11.0},
        }
    )
    assert price == 10.0
    assert timestamp is not None and timestamp.tzinfo is timezone.utc
    assert stale is False

    price, _, stale = choose_snapshot_price({"lastQuote": {"p": 9.0, "P": 11.0}})
    assert price == 10.0
    assert stale is False

    price, _, stale = choose_snapshot_price({"min": {"c": 12.0, "t": 1_700_000_000_000}})
    assert price == 12.0
    assert stale is False

    price, _, stale = choose_snapshot_price({"day": {"c": 13.0}})
    assert price == 13.0
    assert stale is False

    price, _, stale = choose_snapshot_price({"prevDay": {"c": 14.0}})
    assert price == 14.0
    assert stale is True


def test_massive_provider_maps_snapshot_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        assert request.url.params["tickers"] == "AAPL,MSFT"
        return httpx.Response(
            200,
            json={
                "tickers": [
                    {
                        "ticker": "AAPL",
                        "lastTrade": {"p": 190.12, "t": 1_700_000_000_000_000_000},
                        "prevDay": {"c": 189.0},
                        "day": {"o": 188.5, "h": 191.0, "l": 188.0, "v": 12345},
                    },
                    {"ticker": "MSFT", "lastTrade": {"p": 0}, "prevDay": {"c": 430.0}},
                ]
            },
        )

    provider = MassiveMarketDataProvider(
        "test-key",
        stale_after_seconds=999999999.0,
        transport=httpx.MockTransport(handler),
    )

    quotes = run(provider.get_prices({"msft", "aapl"}))

    assert set(quotes) == {"AAPL", "MSFT"}
    assert quotes["AAPL"].price == 190.12
    assert quotes["AAPL"].previous_close == 189.0
    assert quotes["AAPL"].source is MarketSource.MASSIVE
    assert quotes["AAPL"].stale is False
    assert quotes["MSFT"].price == 430.0
    assert quotes["MSFT"].stale is True
    assert provider.health().ok is True


def test_massive_auth_failure_marks_unhealthy_without_quotes() -> None:
    provider = MassiveMarketDataProvider(
        "bad-key",
        transport=httpx.MockTransport(lambda request: httpx.Response(403, json={})),
    )

    assert run(provider.get_prices({"AAPL"})) == {}
    assert provider.health().ok is False
    assert provider.health().source is MarketSource.MASSIVE
    assert provider.health().message == "Massive API authentication failed"


def test_massive_previous_day_bar_maps_ohlcv() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "T": "AAPL",
                        "o": 188.0,
                        "h": 191.0,
                        "l": 187.5,
                        "c": 190.0,
                        "v": 1000,
                        "vw": 189.25,
                        "t": 1_700_000_000_000,
                    }
                ]
            },
        )

    provider = MassiveMarketDataProvider("key", transport=httpx.MockTransport(handler))
    bars = run(provider.get_previous_day_bars({"aapl"}))

    assert bars["AAPL"].low <= bars["AAPL"].open <= bars["AAPL"].high
    assert bars["AAPL"].low <= bars["AAPL"].close <= bars["AAPL"].high
    assert bars["AAPL"].source is MarketSource.MASSIVE
