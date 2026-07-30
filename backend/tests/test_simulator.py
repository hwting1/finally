import asyncio
from datetime import datetime, timezone
from typing import Awaitable, TypeVar

import pytest

from app.market.models import MarketSession, MarketSource
from app.market.service import DEFAULT_WATCHLIST_TICKERS
from app.market.simulator import (
    DEFAULT_SEED_PRICES,
    SimulatedMarketDataProvider,
    seed_price_for_ticker,
)


NOW = datetime(2026, 7, 30, 12, tzinfo=timezone.utc)
T = TypeVar("T")


def provider(seed: int = 42) -> SimulatedMarketDataProvider:
    return SimulatedMarketDataProvider(seed=seed, clock=lambda: NOW)


def run(awaitable: Awaitable[T]) -> T:
    return asyncio.run(awaitable)


def test_same_seed_and_ticker_sequence_is_deterministic() -> None:
    first = provider()
    second = provider()

    for tickers in ({"aapl", "MSFT"}, {"AAPL"}, {"msft", "nvda"}):
        first_prices = run(first.get_prices(tickers))
        second_prices = run(second.get_prices(tickers))
        assert {key: value.price for key, value in first_prices.items()} == {
            key: value.price for key, value in second_prices.items()
        }


def test_unknown_ticker_seed_is_stable_and_normalized() -> None:
    assert seed_price_for_ticker(" xyz ") == seed_price_for_ticker("XYZ")
    assert seed_price_for_ticker("XYZ") == 86.0


def test_quotes_are_normalized_positive_and_bounded() -> None:
    simulator = provider()
    for _ in range(100):
        quote = run(simulator.get_prices({" aapl "}))["AAPL"]
        assert quote.price > 0
        assert quote.previous_price is not None
        assert abs(quote.price / quote.previous_price - 1) <= 0.0203
        assert quote.source is MarketSource.SIMULATOR
        assert quote.session is MarketSession.OPEN
        assert quote.stale is False


def test_previous_price_and_daily_extremes_follow_emitted_quotes() -> None:
    simulator = provider()
    previous = run(simulator.get_prices({"AAPL"}))["AAPL"]
    for _ in range(20):
        current = run(simulator.get_prices({"AAPL"}))["AAPL"]
        assert current.previous_price == previous.price
        assert current.day_low <= current.price <= current.day_high
        assert current.day_low <= current.day_open <= current.day_high
        previous = current


def test_previous_day_bars_have_valid_ohlc_relationships() -> None:
    simulator = provider()
    bars = run(simulator.get_previous_day_bars({"aapl", "NEW"}))

    assert set(bars) == {"AAPL", "NEW"}
    for bar in bars.values():
        assert bar.low <= bar.open <= bar.high
        assert bar.low <= bar.close <= bar.high
        assert bar.volume is not None and 1_000_000 <= bar.volume <= 80_000_000
        assert bar.source is MarketSource.SIMULATOR


def test_health_is_always_ok_and_tracks_success() -> None:
    simulator = provider()
    assert simulator.health().ok is True
    assert simulator.health().last_success_at is None

    run(simulator.get_prices({"SPY"}))

    assert simulator.health().last_success_at == NOW


def test_empty_ticker_collection_returns_empty_result() -> None:
    simulator = provider()
    assert run(simulator.get_prices(set())) == {}
    assert simulator.health().last_success_at == NOW


def test_previous_day_bar_skips_weekend() -> None:
    monday = datetime(2026, 8, 3, 12, tzinfo=timezone.utc)
    simulator = SimulatedMarketDataProvider(clock=lambda: monday)

    bar = run(simulator.get_previous_day_bars({"AAPL"}))["AAPL"]

    assert bar.date == "2026-07-31"


def test_update_interval_must_be_positive() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        SimulatedMarketDataProvider(update_interval_seconds=0)


def test_default_watchlist_tickers_have_explicit_seed_prices() -> None:
    assert DEFAULT_WATCHLIST_TICKERS <= set(DEFAULT_SEED_PRICES)
