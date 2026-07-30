# Massive API Research

Massive is the current name for Polygon.io. New implementation should use `MASSIVE_API_KEY`, `https://api.massive.com`, and the `massive` Python package name when using the official client. Existing Polygon.io keys and the legacy `api.polygon.io` base are reported by the official Python client repository as still supported after the rebrand, but FinAlly should use the Massive names in new code.

Sources:

- REST quickstart: https://massive.com/docs/rest
- Stocks overview: https://massive.com/docs/rest/stocks
- Full market snapshot: https://massive.com/docs/rest/stocks/snapshots/full-market-snapshot
- Unified snapshot: https://massive.com/docs/rest/stocks/snapshots/unified-snapshot
- Previous day bar: https://massive.com/docs/rest/stocks/aggregates/previous-day-bar
- Daily market summary: https://massive.com/docs/rest/stocks/aggregates/daily-market-summary
- Daily ticker summary: https://massive.com/docs/rest/stocks/aggregates/daily-ticker-summary
- Last trade: https://massive.com/docs/rest/stocks/trades-quotes/last-trade
- Last quote: https://massive.com/docs/rest/stocks/trades-quotes/last-quote
- Pricing: https://massive.com/pricing?product=stocks
- Official Python client: https://github.com/massive-com/client-python

## Authentication

Massive REST endpoints accept the API key either as a query parameter or as an authorization header. Use the header form in backend code so logs and traces are less likely to expose the key.

```bash
curl \
  -H "Authorization: Bearer $MASSIVE_API_KEY" \
  "https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,MSFT,NVDA"
```

Equivalent query parameter form:

```bash
curl \
  "https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,MSFT,NVDA&apiKey=$MASSIVE_API_KEY"
```

## Plan Access And Rate-Limit Implications

Massive pricing currently lists Stocks Basic Free at 5 API calls per minute, 2 years of historical data, and end-of-day data. Paid individual stock plans advertise unlimited API calls, with Starter and Developer at 15-minute delayed data and Advanced at real-time data.

For FinAlly:

- The default experience must be the simulator. It should not require Massive.
- When `MASSIVE_API_KEY` is set, use REST polling only. Do not use WebSockets for this project.
- The REST polling interval must default to at least 15 seconds to stay comfortably within free-tier constraints when one call retrieves all watched tickers.
- The user-facing stream cadence can remain faster than the Massive polling cadence by replaying the latest cached values and marking stale/closed-market data.
- Do not silently switch from real prices to simulated prices when markets are closed or when an API response is stale. Preserve the source and stale flags.

## Recommended Endpoint For Current Multi-Ticker Prices

Use the full market snapshot endpoint with the `tickers` query parameter:

```text
GET /v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,MSFT,NVDA
```

Why this endpoint:

- It accepts a comma-separated list of tickers, which fits FinAlly's watchlist plus positions universe.
- It returns one consolidated response with `lastTrade`, `lastQuote`, `min`, `day`, `prevDay`, `todaysChange`, `todaysChangePerc`, and `updated`.
- Snapshot data has plan-dependent recency: not included on some free/basic access, delayed on Starter/Developer, and real-time on Advanced.

Response fields to use:

| Massive field | FinAlly use |
|---|---|
| `ticker` | Canonical ticker symbol |
| `lastTrade.p` | Preferred live transaction price when available |
| `lastTrade.t` | Preferred price timestamp; nanosecond Unix timestamp |
| `lastQuote.p`, `lastQuote.P` | Bid and ask; midpoint fallback when trade is unavailable |
| `lastQuote.t` | Quote timestamp; nanosecond Unix timestamp |
| `min.c` | Most recent minute close fallback |
| `min.t` | Minute-bar timestamp; millisecond Unix timestamp |
| `day.c` | Current day close/last aggregate fallback |
| `prevDay.c` | Previous close baseline |
| `todaysChange` | Vendor-provided absolute change |
| `todaysChangePerc` | Vendor-provided daily percent change |
| `updated` | Last update timestamp, usually nanoseconds |

Price selection order:

1. `lastTrade.p`, if present and positive.
2. Quote midpoint `(lastQuote.p + lastQuote.P) / 2`, if both bid and ask are present and positive.
3. `min.c`, if present and positive.
4. `day.c`, if present and positive.
5. `prevDay.c`, only as a stale fallback.

Example direct `httpx` client:

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

import httpx


BASE_URL = "https://api.massive.com"


def ns_to_datetime(value: int | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1_000_000_000, tz=timezone.utc)


def ms_to_datetime(value: int | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1_000, tz=timezone.utc)


def choose_snapshot_price(snapshot: dict) -> tuple[float | None, datetime | None, bool]:
    last_trade = snapshot.get("lastTrade") or {}
    if last_trade.get("p"):
        return float(last_trade["p"]), ns_to_datetime(last_trade.get("t")), False

    last_quote = snapshot.get("lastQuote") or {}
    bid = last_quote.get("p")
    ask = last_quote.get("P")
    if bid and ask:
        return (float(bid) + float(ask)) / 2, ns_to_datetime(last_quote.get("t")), False

    minute = snapshot.get("min") or {}
    if minute.get("c"):
        return float(minute["c"]), ms_to_datetime(minute.get("t")), False

    day = snapshot.get("day") or {}
    if day.get("c"):
        return float(day["c"]), None, False

    prev_day = snapshot.get("prevDay") or {}
    if prev_day.get("c"):
        return float(prev_day["c"]), None, True

    return None, None, True


async def fetch_snapshots(api_key: str, tickers: Iterable[str]) -> list[dict]:
    symbols = ",".join(sorted({ticker.upper() for ticker in tickers}))
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        response = await client.get(
            "/v2/snapshot/locale/us/markets/stocks/tickers",
            params={"tickers": symbols},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        response.raise_for_status()
        payload = response.json()
    return payload.get("tickers", [])
```

## Unified Snapshot Alternative

The newer unified snapshot endpoint is:

```text
GET /v3/snapshot?type=stocks&ticker=AAPL&limit=250
```

It returns cross-asset snapshot records with fields such as `session.price`, `session.previous_close`, `session.change`, `session.change_percent`, `market_status`, `last_trade`, `last_quote`, and `last_minute`.

Use it later if FinAlly expands beyond U.S. stocks or needs `market_status` directly from the API. For the initial project, the v2 full market snapshot is simpler because it directly supports a comma-separated `tickers` filter in one call.

## Single-Ticker Current Price Endpoints

These are useful for diagnostics, but avoid them in the poller because they cost one request per ticker.

Last trade:

```text
GET /v2/last/trade/{stocksTicker}
```

Last quote:

```text
GET /v2/last/nbbo/{stocksTicker}
```

Use these only for debugging a ticker-specific discrepancy or a future detailed quote panel.

## End-Of-Day Prices

Use previous day bar when the app needs yesterday's close for one ticker:

```text
GET /v2/aggs/ticker/{stocksTicker}/prev?adjusted=true
```

The response contains an array of OHLCV bars. The first result includes:

| Field | Meaning |
|---|---|
| `T` | Ticker |
| `o` | Open |
| `h` | High |
| `l` | Low |
| `c` | Close |
| `v` | Volume |
| `vw` | VWAP |
| `t` | Millisecond timestamp |

Example:

```python
async def fetch_previous_close(api_key: str, ticker: str) -> dict | None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        response = await client.get(
            f"/v2/aggs/ticker/{ticker.upper()}/prev",
            params={"adjusted": "true"},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        response.raise_for_status()
        payload = response.json()
    results = payload.get("results") or []
    return results[0] if results else None
```

Use daily market summary when the app needs EOD OHLCV for many tickers on a known date:

```text
GET /v2/aggs/grouped/locale/us/market/stocks/{date}?adjusted=true&include_otc=false
```

This returns all U.S. stock daily bars for the date. Because it is a market-wide response, it is efficient for bulk EOD hydration but heavier to parse than the snapshot endpoint.

Use daily ticker summary when the app needs a specific calendar date for a specific ticker, including pre-market and after-hours fields:

```text
GET /v1/open-close/{stocksTicker}/{date}?adjusted=true
```

## Official Python Client

Massive publishes an official Python client:

```bash
pip install -U massive
```

Basic usage:

```python
from massive import RESTClient

client = RESTClient(api_key="YOUR_API_KEY")

trade = client.get_last_trade(ticker="AAPL")
quote = client.get_last_quote(ticker="AAPL")

bars = list(
    client.list_aggs(
        ticker="AAPL",
        multiplier=1,
        timespan="day",
        from_="2026-07-01",
        to="2026-07-30",
        adjusted=True,
        limit=50000,
    )
)
```

Recommendation for FinAlly: use direct `httpx` calls for the first implementation. The project only needs two or three REST endpoints, and direct calls keep the response mapping explicit for teaching. The official client is still appropriate if a future agent adds WebSockets or broad historical-data tooling.

## Error Handling

Implement these behaviors in the Massive adapter:

- `401` or `403`: mark the provider unhealthy and expose a clear configuration/authentication error. Do not fall back to simulator inside the same process because that hides a bad key.
- `429`: honor `Retry-After` if present, otherwise back off exponentially with jitter and keep serving stale cache values.
- `5xx` and network errors: retry with bounded backoff; keep stale cache values; set provider health to degraded.
- Missing ticker in response: leave the previous cache entry untouched if present; otherwise emit an unavailable entry for that ticker.
- Empty `tickers` request: skip network call.
- Invalid symbol from the user: normalize to uppercase in the interface, but preserve a validation error if Massive returns no data after one or two polls.

## Timestamp Handling

Massive uses both nanosecond and millisecond Unix timestamps depending on endpoint and field:

- `lastTrade.t`, `lastQuote.t`, and v3 `last_trade.last_updated` are nanoseconds.
- Aggregate bar timestamps such as `min.t` and previous-day `results[].t` are milliseconds.

Convert everything to timezone-aware UTC `datetime` objects at the adapter boundary. The rest of the backend should not know about Massive timestamp units.

