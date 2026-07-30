"""Serialization helpers for market data API payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.market.models import MarketProviderHealth, PriceQuote


def utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def quote_to_payload(quote: PriceQuote) -> dict[str, Any]:
    return {
        "ticker": quote.ticker,
        "price": quote.price,
        "previous_price": quote.previous_price,
        "previous_close": quote.previous_close,
        "change": quote.change,
        "change_percent": quote.change_percent,
        "direction": quote.direction,
        "timestamp": utc_iso(quote.timestamp),
        "stale": quote.stale,
        "source": quote.source.value,
        "session": quote.session.value,
        "volume": quote.volume,
        "day_open": quote.day_open,
        "day_high": quote.day_high,
        "day_low": quote.day_low,
    }


def health_to_payload(health: MarketProviderHealth) -> dict[str, Any]:
    return {
        "source": health.source.value,
        "ok": health.ok,
        "message": health.message,
        "last_success_at": utc_iso(health.last_success_at),
        "last_error_at": utc_iso(health.last_error_at),
    }
