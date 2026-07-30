"""Massive REST market data provider."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.market.models import (
    DailyBar,
    MarketProviderHealth,
    MarketSession,
    MarketSource,
    PriceQuote,
)
from app.market.validation import normalize_ticker_set


BASE_URL = "https://api.massive.com"


def ns_to_datetime(value: int | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1_000_000_000, tz=timezone.utc)


def ms_to_datetime(value: int | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1_000, tz=timezone.utc)


def _positive_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def choose_snapshot_price(snapshot: dict[str, Any]) -> tuple[float | None, datetime | None, bool]:
    last_trade = snapshot.get("lastTrade") or {}
    trade_price = _positive_float(last_trade.get("p"))
    if trade_price is not None:
        return trade_price, ns_to_datetime(last_trade.get("t")), False

    last_quote = snapshot.get("lastQuote") or {}
    bid = _positive_float(last_quote.get("p"))
    ask = _positive_float(last_quote.get("P"))
    if bid is not None and ask is not None:
        return (bid + ask) / 2, ns_to_datetime(last_quote.get("t")), False

    minute = snapshot.get("min") or {}
    minute_close = _positive_float(minute.get("c"))
    if minute_close is not None:
        return minute_close, ms_to_datetime(minute.get("t")), False

    day = snapshot.get("day") or {}
    day_close = _positive_float(day.get("c"))
    if day_close is not None:
        return day_close, None, False

    prev_day = snapshot.get("prevDay") or {}
    previous_close = _positive_float(prev_day.get("c"))
    if previous_close is not None:
        return previous_close, None, True

    return None, None, True


class MassiveMarketDataProvider:
    def __init__(
        self,
        api_key: str,
        *,
        stale_after_seconds: float = 30.0,
        base_url: str = BASE_URL,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._stale_after_seconds = stale_after_seconds
        self._base_url = base_url
        self._transport = transport
        self._health = MarketProviderHealth(
            source=MarketSource.MASSIVE,
            ok=True,
            message="massive provider configured",
        )

    async def get_prices(self, tickers: set[str]) -> dict[str, PriceQuote]:
        symbols = normalize_ticker_set(tickers)
        if not symbols:
            return {}

        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=10.0,
                transport=self._transport,
            ) as client:
                response = await client.get(
                    "/v2/snapshot/locale/us/markets/stocks/tickers",
                    params={"tickers": ",".join(sorted(symbols))},
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
            if response.status_code != 200:
                self._mark_http_error(response.status_code)
                return {}
            payload = response.json()
        except httpx.HTTPError as exc:
            self._mark_unhealthy(f"Massive API network error: {exc.__class__.__name__}")
            return {}

        quotes: dict[str, PriceQuote] = {}
        now = datetime.now(timezone.utc)
        for snapshot in payload.get("tickers", []) or []:
            quote = self._quote_from_snapshot(snapshot, now)
            if quote is not None:
                quotes[quote.ticker] = quote

        self._health = MarketProviderHealth(
            source=MarketSource.MASSIVE,
            ok=True,
            message="massive provider healthy",
            last_success_at=now,
            last_error_at=self._health.last_error_at,
        )
        return quotes

    async def get_previous_day_bars(self, tickers: set[str]) -> dict[str, DailyBar]:
        symbols = normalize_ticker_set(tickers)
        bars: dict[str, DailyBar] = {}
        for symbol in sorted(symbols):
            bar = await self._fetch_previous_day_bar(symbol)
            if bar is not None:
                bars[symbol] = bar
        return bars

    def health(self) -> MarketProviderHealth:
        return self._health

    def _quote_from_snapshot(
        self, snapshot: dict[str, Any], fallback_timestamp: datetime
    ) -> PriceQuote | None:
        ticker = str(snapshot.get("ticker") or "").strip().upper()
        if not ticker:
            return None
        price, timestamp, stale = choose_snapshot_price(snapshot)
        if price is None:
            return None

        prev_day = snapshot.get("prevDay") or {}
        day = snapshot.get("day") or {}
        minute = snapshot.get("min") or {}
        previous_close = _positive_float(prev_day.get("c"))
        timestamp = timestamp or ns_to_datetime(snapshot.get("updated")) or fallback_timestamp
        age = (datetime.now(timezone.utc) - timestamp).total_seconds()
        stale = stale or age > self._stale_after_seconds

        return PriceQuote(
            ticker=ticker,
            price=round(price, 4),
            previous_price=None,
            previous_close=previous_close,
            timestamp=timestamp,
            source=MarketSource.MASSIVE,
            session=MarketSession.UNKNOWN,
            stale=stale,
            volume=_positive_float(day.get("v") or minute.get("v")),
            day_open=_positive_float(day.get("o")),
            day_high=_positive_float(day.get("h")),
            day_low=_positive_float(day.get("l")),
        )

    async def _fetch_previous_day_bar(self, ticker: str) -> DailyBar | None:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=10.0,
                transport=self._transport,
            ) as client:
                response = await client.get(
                    f"/v2/aggs/ticker/{ticker}/prev",
                    params={"adjusted": "true"},
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
            if response.status_code != 200:
                self._mark_http_error(response.status_code)
                return None
            results = response.json().get("results") or []
        except httpx.HTTPError as exc:
            self._mark_unhealthy(f"Massive API network error: {exc.__class__.__name__}")
            return None
        if not results:
            return None
        raw = results[0]
        open_price = _positive_float(raw.get("o"))
        high = _positive_float(raw.get("h"))
        low = _positive_float(raw.get("l"))
        close = _positive_float(raw.get("c"))
        if None in (open_price, high, low, close):
            return None
        timestamp = ms_to_datetime(raw.get("t")) or datetime.now(timezone.utc)
        return DailyBar(
            ticker=str(raw.get("T") or ticker).upper(),
            date=timestamp.date().isoformat(),
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=_positive_float(raw.get("v")),
            vwap=_positive_float(raw.get("vw")),
            source=MarketSource.MASSIVE,
            adjusted=True,
        )

    def _mark_http_error(self, status: int) -> None:
        if status in (401, 403):
            self._mark_unhealthy("Massive API authentication failed")
        elif status == 429:
            self._mark_unhealthy("Massive API rate limited")
        elif status >= 500:
            self._mark_unhealthy(f"Massive API server error {status}")
        else:
            self._mark_unhealthy(f"Massive API error {status}")

    def _mark_unhealthy(self, message: str) -> None:
        self._health = MarketProviderHealth(
            source=MarketSource.MASSIVE,
            ok=False,
            message=message,
            last_success_at=self._health.last_success_at,
            last_error_at=datetime.now(timezone.utc),
        )
