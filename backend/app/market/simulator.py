"""Deterministic, in-memory equity price simulator."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import exp, sqrt
from typing import Callable

from app.market.models import (
    DailyBar,
    MarketProviderHealth,
    MarketSession,
    MarketSource,
    PriceQuote,
)

DEFAULT_SEED_PRICES = {
    "AAPL": 190.00,
    "MSFT": 430.00,
    "NVDA": 120.00,
    "GOOGL": 175.00,
    "AMZN": 185.00,
    "META": 500.00,
    "TSLA": 250.00,
    "NFLX": 650.00,
    "AMD": 160.00,
    "SPY": 550.00,
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ticker_value(ticker: str) -> int:
    return sum((index + 1) * ord(char) for index, char in enumerate(ticker))


def seed_price_for_ticker(ticker: str) -> float:
    """Return a stable starting price for any normalized or mixed-case symbol."""
    normalized = ticker.strip().upper()
    if normalized in DEFAULT_SEED_PRICES:
        return DEFAULT_SEED_PRICES[normalized]
    return round(25.0 + (_ticker_value(normalized) % 475), 2)


@dataclass(slots=True)
class SimulatedTickerState:
    ticker: str
    price: float
    previous_price: float
    previous_close: float
    day_open: float
    day_high: float
    day_low: float
    volume: float
    beta: float
    updated_at: datetime


class SimulatedMarketDataProvider:
    """Generate repeatable quotes without network access or API credentials."""

    def __init__(
        self,
        seed: int = 42,
        *,
        update_interval_seconds: float = 0.5,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if update_interval_seconds <= 0:
            raise ValueError("update_interval_seconds must be positive")
        self._seed = seed
        self._market_rng = random.Random(seed)
        self._ticker_rngs: dict[str, random.Random] = {}
        self._states: dict[str, SimulatedTickerState] = {}
        self._update_interval_seconds = update_interval_seconds
        self._clock = clock
        self._last_success_at: datetime | None = None

    @staticmethod
    def _normalize_tickers(tickers: set[str]) -> list[str]:
        return sorted({ticker.strip().upper() for ticker in tickers if ticker.strip()})

    def _rng_for(self, ticker: str) -> random.Random:
        return self._ticker_rngs.setdefault(
            ticker, random.Random(self._seed + _ticker_value(ticker))
        )

    def _state_for(self, ticker: str, now: datetime) -> SimulatedTickerState:
        existing = self._states.get(ticker)
        if existing is not None:
            return existing

        price = seed_price_for_ticker(ticker)
        rng = self._rng_for(ticker)
        previous_close = round(price * rng.uniform(0.98, 1.02), 2)
        state = SimulatedTickerState(
            ticker=ticker,
            price=price,
            previous_price=price,
            previous_close=previous_close,
            day_open=price,
            day_high=price,
            day_low=price,
            volume=float(rng.randint(1_000_000, 10_000_000)),
            beta=rng.uniform(0.7, 1.3),
            updated_at=now,
        )
        self._states[ticker] = state
        return state

    def _advance(
        self, state: SimulatedTickerState, market_move: float, now: datetime
    ) -> SimulatedTickerState:
        trading_seconds_per_year = 252 * 6.5 * 60 * 60
        dt_years = self._update_interval_seconds / trading_seconds_per_year
        rng = self._rng_for(state.ticker)
        drift = 0.05 * dt_years
        sigma = 0.20 * sqrt(dt_years)
        raw_return = drift + state.beta * market_move + rng.gauss(0.0, sigma)
        bounded_return = max(-0.02, min(0.02, raw_return))
        price = round(max(0.01, state.price * exp(bounded_return)), 2)
        return SimulatedTickerState(
            ticker=state.ticker,
            price=price,
            previous_price=state.price,
            previous_close=state.previous_close,
            day_open=state.day_open,
            day_high=max(state.day_high, price),
            day_low=min(state.day_low, price),
            volume=state.volume + rng.randint(100, 10_000),
            beta=state.beta,
            updated_at=now,
        )

    async def get_prices(self, tickers: set[str]) -> dict[str, PriceQuote]:
        normalized = self._normalize_tickers(tickers)
        now = self._clock()
        if not normalized:
            self._last_success_at = now
            return {}

        trading_seconds_per_year = 252 * 6.5 * 60 * 60
        market_sigma = 0.20 * sqrt(self._update_interval_seconds / trading_seconds_per_year) * 0.35
        market_move = self._market_rng.gauss(0.0, market_sigma)
        quotes: dict[str, PriceQuote] = {}
        for ticker in normalized:
            state = self._advance(self._state_for(ticker, now), market_move, now)
            self._states[ticker] = state
            quotes[ticker] = PriceQuote(
                ticker=ticker,
                price=state.price,
                previous_price=state.previous_price,
                previous_close=state.previous_close,
                timestamp=state.updated_at,
                source=MarketSource.SIMULATOR,
                session=MarketSession.OPEN,
                stale=False,
                volume=state.volume,
                day_open=state.day_open,
                day_high=state.day_high,
                day_low=state.day_low,
            )
        self._last_success_at = now
        return quotes

    async def get_previous_day_bars(self, tickers: set[str]) -> dict[str, DailyBar]:
        now = self._clock()
        bars: dict[str, DailyBar] = {}
        for ticker in self._normalize_tickers(tickers):
            state = self._state_for(ticker, now)
            rng = random.Random(self._seed * 10_007 + _ticker_value(ticker))
            close = state.previous_close
            open_price = close * rng.uniform(0.98, 1.02)
            high = max(open_price, close) * rng.uniform(1.0, 1.03)
            low = min(open_price, close) * rng.uniform(0.97, 1.0)
            open_price, high, low = map(lambda value: round(value, 2), (open_price, high, low))
            close = round(close, 2)
            previous_trading_day = now.date() - timedelta(days=1)
            while previous_trading_day.weekday() >= 5:
                previous_trading_day -= timedelta(days=1)
            bars[ticker] = DailyBar(
                ticker=ticker,
                date=previous_trading_day.isoformat(),
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=float(rng.randint(1_000_000, 80_000_000)),
                vwap=round((open_price + high + low + close) / 4, 2),
                source=MarketSource.SIMULATOR,
            )
        self._last_success_at = now
        return bars

    def health(self) -> MarketProviderHealth:
        return MarketProviderHealth(
            source=MarketSource.SIMULATOR,
            ok=True,
            last_success_at=self._last_success_at,
        )
