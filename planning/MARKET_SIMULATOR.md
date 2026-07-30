# Market Simulator

The simulator is FinAlly's default market data provider. It lets the app run with no API keys, no network dependency, repeatable demos, and deterministic tests. It implements the same `MarketDataProvider` protocol documented in `planning/MARKET_INTERFACE.md`.

## Design Goals

- Produce plausible equity-like price movement without pretending to be real data.
- Keep behavior deterministic by default so tests and recordings are stable.
- Update quickly enough for visible price flashes and sparklines.
- Avoid impossible prices, extreme jumps, and synchronized movement across every ticker.
- Keep the model understandable for students reading the backend code.

## Non-Goals

- The simulator is not a backtesting engine.
- It does not need market microstructure, order books, bid/ask spread modeling, dividends, splits, halts, or real trading calendars.
- It should not use live data implicitly. If the Massive API is unavailable after startup, keep the Massive provider degraded rather than switching to simulation.

## Suggested Module

```text
backend/app/market/simulator.py
```

The module should expose:

```python
class SimulatedMarketDataProvider:
    async def get_prices(self, tickers: set[str]) -> dict[str, PriceQuote]:
        ...

    async def get_previous_day_bars(self, tickers: set[str]) -> dict[str, DailyBar]:
        ...

    def health(self) -> MarketProviderHealth:
        ...
```

## Seed Prices

Use realistic static starting prices for default watchlist tickers. These are not live prices; they are stable teaching/demo anchors.

```python
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
```

For unknown tickers, derive a deterministic starting price from the ticker string:

```python
def seed_price_for_ticker(ticker: str) -> float:
    value = sum((index + 1) * ord(char) for index, char in enumerate(ticker))
    return round(25.0 + (value % 475), 2)
```

## Price Process

Use a simple geometric random walk with a weak shared market factor.

At each tick:

```text
new_price = old_price * exp(drift + market_move * beta + idiosyncratic_move)
```

Recommended defaults:

| Parameter | Default | Purpose |
|---|---:|---|
| Update interval | 0.5 seconds | UI movement and sparkline growth |
| Annualized volatility | 20% | Plausible large-cap equity motion |
| Annualized drift | 5% | Tiny upward bias |
| Trading seconds per year | 252 * 6.5 * 60 * 60 | Scales GBM movement |
| Market factor volatility share | 35% | Prevents fully independent ticker motion |
| Per-ticker beta | 0.7 to 1.3 | Slightly different market sensitivity |
| Price floor | 0.01 | Prevents invalid prices |
| Per-tick move clamp | +/-2% | Avoids visually absurd jumps |

Because the simulator updates every 0.5 seconds while real markets do not trade continuously every half second for every ticker, clamp the movement. The goal is plausible UI behavior, not statistical purity.

## Determinism

Use a deterministic random generator, not global `random`.

```python
import random


class SimulatedMarketDataProvider:
    def __init__(self, seed: int = 42) -> None:
        self._rng = random.Random(seed)
```

If tests need total reproducibility across dynamic ticker order, use a per-ticker RNG:

```python
def ticker_seed(global_seed: int, ticker: str) -> int:
    return global_seed + sum((index + 1) * ord(char) for index, char in enumerate(ticker))
```

Store one ticker state per uppercase symbol.

```python
from dataclasses import dataclass
from datetime import datetime


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
```

## Session Model

Keep the initial implementation simple:

- The simulator is always `session="open"` while the backend is running.
- It produces fresh timestamps on every update.
- It sets `stale=false`.
- It returns `source="simulator"`.

Optional future enhancement:

- Add a fake 6.5-hour session clock compressed into a shorter demo cycle.
- Reset `day_open`, `day_high`, `day_low`, and `volume` at each simulated open.
- Emit `premarket`, `open`, `after_hours`, and `closed` states.

Do not add this until core trading and SSE behavior are stable.

## Update Algorithm

```python
from datetime import datetime, timezone
from math import exp


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def next_state(
    state: SimulatedTickerState,
    market_move: float,
    rng: random.Random,
    dt_years: float,
) -> SimulatedTickerState:
    drift = 0.05 * dt_years
    sigma = 0.20 * (dt_years ** 0.5)
    idiosyncratic = rng.gauss(0.0, sigma)
    raw_return = drift + state.beta * market_move + idiosyncratic
    bounded_return = clamp(raw_return, -0.02, 0.02)
    new_price = max(0.01, state.price * exp(bounded_return))
    new_price = round(new_price, 2)

    return SimulatedTickerState(
        ticker=state.ticker,
        price=new_price,
        previous_price=state.price,
        previous_close=state.previous_close,
        day_open=state.day_open,
        day_high=max(state.day_high, new_price),
        day_low=min(state.day_low, new_price),
        volume=state.volume + rng.randint(100, 10_000),
        beta=state.beta,
        updated_at=datetime.now(timezone.utc),
    )
```

`get_prices(tickers)` should advance the requested ticker states once per call and return `PriceQuote` objects. The market service loop controls call cadence.

## Previous Day Bars

The simulator can synthesize previous-day bars from seed prices.

For each ticker:

- `close = state.previous_close`
- `open = close * deterministic factor between 0.98 and 1.02`
- `high = max(open, close) * deterministic factor between 1.00 and 1.03`
- `low = min(open, close) * deterministic factor between 0.97 and 1.00`
- `volume = deterministic integer between 1,000,000 and 80,000,000`
- `vwap = (open + high + low + close) / 4`

This is enough for baseline comparisons and portfolio P&L. It does not need to match the live random walk exactly.

## Behavior For New Watchlist Tickers

When the user or LLM adds a ticker:

1. Normalize it to uppercase.
2. If state already exists, return the existing state.
3. If not, create a new deterministic state from the ticker seed.
4. Include the ticker in the next provider update and SSE batch.

This makes newly added tickers appear immediately without network calls.

## Generated Quote Mapping

For each ticker state, generate:

```python
PriceQuote(
    ticker=state.ticker,
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
```

The quote object's computed `change`, `change_percent`, and `direction` properties should drive frontend color and P&L display.

## Testing Requirements

Unit tests:

- Same seed and same ticker sequence produce the same prices.
- Unknown ticker seed price is stable.
- Prices stay positive.
- Per-tick changes are bounded.
- `previous_price` is the last emitted `price`.
- `day_high` and `day_low` update correctly.
- `get_previous_day_bars()` returns valid OHLC relationships: `low <= open/close <= high`.
- Provider health is always ok.

Integration tests:

- With no `MASSIVE_API_KEY`, provider selection returns the simulator.
- SSE emits simulator prices within one second.
- Market order fills use the simulator cache price.
- Adding a ticker adds it to the next emitted price batch.

## Implementation Guardrails

- Do not fetch real prices in simulator mode.
- Do not import Massive client code from `simulator.py`.
- Do not use wall-clock randomness that makes tests flaky.
- Do not model transaction execution inside the simulator. Trade execution belongs to portfolio/order services and reads from the market cache.
- Keep the simulator state in memory. The database stores trades, positions, watchlist, and user cash, not simulated market state.

