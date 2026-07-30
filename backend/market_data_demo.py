"""Interactive terminal demo for the FinAlly market data simulator.

Run from the backend directory:

    uv run python market_data_demo.py
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from time import monotonic

from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from app.market.models import PriceQuote
from app.market.service import DEFAULT_WATCHLIST_TICKERS
from app.market.simulator import DEFAULT_SEED_PRICES, SimulatedMarketDataProvider


RUN_SECONDS = 60.0
UPDATE_INTERVAL_SECONDS = 0.5
SPARKLINE_WIDTH = 24
MAX_EVENTS = 10
NOTABLE_TICK_CHANGE_PERCENT = 0.04
NOTABLE_SESSION_CHANGE_PERCENT = 0.20

TICKERS = tuple(ticker for ticker in DEFAULT_SEED_PRICES if ticker in DEFAULT_WATCHLIST_TICKERS)
SPARK_CHARS = "▁▂▃▄▅▆▇█"


@dataclass
class TickerState:
    seed_price: float
    history: deque[float] = field(default_factory=lambda: deque(maxlen=SPARKLINE_WIDTH))
    events: int = 0
    max_price: float = 0.0
    min_price: float = 0.0


def money(value: float) -> str:
    return f"${value:,.2f}"


def pct(value: float) -> str:
    return f"{value:+.2f}%"


def direction_text(quote: PriceQuote) -> Text:
    if quote.direction == "up":
        return Text("▲", style="bold green")
    if quote.direction == "down":
        return Text("▼", style="bold red")
    return Text("▶", style="bold yellow")


def price_style(quote: PriceQuote) -> str:
    if quote.direction == "up":
        return "bold green"
    if quote.direction == "down":
        return "bold red"
    return "bold yellow"


def sparkline(values: deque[float], style: str) -> Text:
    if not values:
        return Text(" " * SPARKLINE_WIDTH, style=style)

    low = min(values)
    high = max(values)
    if high == low:
        return Text(SPARK_CHARS[3] * len(values), style=style)

    chars = []
    scale = len(SPARK_CHARS) - 1
    for value in values:
        index = round((value - low) / (high - low) * scale)
        chars.append(SPARK_CHARS[index])
    return Text("".join(chars).ljust(SPARKLINE_WIDTH), style=style)


def session_change_percent(quote: PriceQuote, state: TickerState) -> float:
    return (quote.price - state.seed_price) / state.seed_price * 100.0


def tick_change_percent(quote: PriceQuote) -> float:
    if quote.previous_price in (None, 0):
        return 0.0
    return (quote.price - quote.previous_price) / quote.previous_price * 100.0


def maybe_record_event(
    quote: PriceQuote,
    state: TickerState,
    event_log: deque[Text],
) -> None:
    tick_move = tick_change_percent(quote)
    session_move = session_change_percent(quote, state)
    notable_tick = abs(tick_move) >= NOTABLE_TICK_CHANGE_PERCENT
    notable_session = abs(session_move) >= NOTABLE_SESSION_CHANGE_PERCENT
    new_high = quote.price >= state.max_price and len(state.history) > 1
    new_low = quote.price <= state.min_price and len(state.history) > 1

    if not (notable_tick or notable_session or new_high or new_low):
        return

    state.events += 1
    timestamp = datetime.now().strftime("%H:%M:%S")
    style = "green" if quote.price >= state.seed_price else "red"
    reason = "tick"
    if new_high:
        reason = "new high"
    elif new_low:
        reason = "new low"
    elif notable_session:
        reason = "session"

    event_log.appendleft(
        Text.assemble(
            (timestamp, "dim"),
            "  ",
            (quote.ticker.ljust(5), "bold"),
            " ",
            (reason.ljust(8), "cyan"),
            " ",
            (money(quote.price).rjust(10), style),
            " ",
            (pct(tick_move).rjust(8), "green" if tick_move >= 0 else "red"),
            " tick  ",
            (pct(session_move).rjust(8), style),
            " session",
        )
    )


def build_dashboard(
    quotes: dict[str, PriceQuote],
    states: dict[str, TickerState],
    event_log: deque[Text],
    elapsed: float,
) -> Group:
    remaining = max(0.0, RUN_SECONDS - elapsed)
    title = Text.assemble(
        ("FinAlly Market Data Simulator", "bold #ecad0a"),
        ("  GBM random walk  ", "dim"),
        (f"{remaining:04.1f}s remaining", "bold cyan"),
    )

    table = Table(expand=True, show_lines=False, header_style="bold #209dd7")
    table.add_column("Ticker", style="bold")
    table.add_column("Dir", justify="center")
    table.add_column("Price", justify="right")
    table.add_column("Tick", justify="right")
    table.add_column("Session", justify="right")
    table.add_column("High", justify="right")
    table.add_column("Low", justify="right")
    table.add_column("Sparkline", no_wrap=True)

    for ticker in TICKERS:
        quote = quotes[ticker]
        state = states[ticker]
        tick_move = tick_change_percent(quote)
        session_move = session_change_percent(quote, state)
        style = price_style(quote)
        session_style = "green" if session_move >= 0 else "red"
        table.add_row(
            ticker,
            direction_text(quote),
            Text(money(quote.price), style=style),
            Text(pct(tick_move), style="green" if tick_move >= 0 else "red"),
            Text(pct(session_move), style=session_style),
            money(state.max_price),
            money(state.min_price),
            sparkline(state.history, session_style),
        )

    events = list(event_log) or [Text("Waiting for notable moves...", style="dim")]
    event_panel = Panel(
        Group(*events),
        title="Event Log",
        border_style="#753991",
        height=MAX_EVENTS + 2,
    )

    return Group(Panel(Align.center(title), border_style="#209dd7"), table, event_panel)


def print_summary(
    console: Console,
    states: dict[str, TickerState],
    final_quotes: dict[str, PriceQuote],
    elapsed: float,
) -> None:
    table = Table(title="Session Summary", header_style="bold #209dd7")
    table.add_column("Ticker", style="bold")
    table.add_column("Seed", justify="right")
    table.add_column("Final", justify="right")
    table.add_column("Change", justify="right")
    table.add_column("High", justify="right")
    table.add_column("Low", justify="right")
    table.add_column("Events", justify="right")

    winners: list[tuple[str, float]] = []
    for ticker in TICKERS:
        quote = final_quotes[ticker]
        state = states[ticker]
        change = session_change_percent(quote, state)
        winners.append((ticker, change))
        style = "green" if change >= 0 else "red"
        table.add_row(
            ticker,
            money(state.seed_price),
            money(quote.price),
            Text(pct(change), style=style),
            money(state.max_price),
            money(state.min_price),
            str(state.events),
        )

    leader = max(winners, key=lambda item: item[1])
    laggard = min(winners, key=lambda item: item[1])
    console.print()
    console.print(table)
    console.print(
        Panel(
            Text.assemble(
                ("Runtime: ", "bold"),
                (f"{elapsed:.1f}s", "cyan"),
                ("   Leader: ", "bold"),
                (f"{leader[0]} {pct(leader[1])}", "green"),
                ("   Laggard: ", "bold"),
                (f"{laggard[0]} {pct(laggard[1])}", "red"),
            ),
            border_style="#ecad0a",
        )
    )


async def run_demo() -> None:
    console = Console()
    simulator = SimulatedMarketDataProvider(update_interval_seconds=UPDATE_INTERVAL_SECONDS)
    states = {
        ticker: TickerState(seed_price=DEFAULT_SEED_PRICES[ticker])
        for ticker in TICKERS
    }
    event_log: deque[Text] = deque(maxlen=MAX_EVENTS)
    final_quotes: dict[str, PriceQuote] = {}
    start = monotonic()

    try:
        with Live(console=console, refresh_per_second=8, screen=True) as live:
            while monotonic() - start < RUN_SECONDS:
                quotes = await simulator.get_prices(set(TICKERS))
                final_quotes = quotes

                for ticker, quote in quotes.items():
                    state = states[ticker]
                    state.history.append(quote.price)
                    state.max_price = max(state.max_price or quote.price, quote.price)
                    state.min_price = min(state.min_price or quote.price, quote.price)
                    maybe_record_event(quote, state, event_log)

                live.update(build_dashboard(quotes, states, event_log, monotonic() - start))
                await asyncio.sleep(UPDATE_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        event_log.appendleft(Text("Interrupted by Ctrl+C", style="bold yellow"))

    elapsed = monotonic() - start
    if not final_quotes:
        final_quotes = await simulator.get_prices(set(TICKERS))
        for ticker, quote in final_quotes.items():
            state = states[ticker]
            state.history.append(quote.price)
            state.max_price = quote.price
            state.min_price = quote.price

    print_summary(console, states, final_quotes, elapsed)


if __name__ == "__main__":
    asyncio.run(run_demo())
