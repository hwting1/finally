"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { addWatchlistTicker, EndpointUnavailableError, executeTrade, getHealth, getMarketPrice, getMarketPrices, getPortfolio, removeWatchlistTicker, sendChatMessage } from "@/lib/api";
import { formatCurrency, formatNumber, formatPercent, isTicker, normalizeTicker } from "@/lib/format";
import { applyLocalTrade, buildPositionViews, portfolioTotal, quoteMap, STARTING_CASH } from "@/lib/portfolio";
import type { ChatMessage, PortfolioResponse, PortfolioSnapshot, Position, PriceQuote, PriceStreamPayload, TradeSide } from "@/lib/types";
import { Heatmap, LineChart, Sparkline } from "./Charts";

const DEFAULT_TICKERS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"];
const MAX_SERIES = 120;

function nowLabel() {
  return new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function mapPortfolio(payload: PortfolioResponse): { cash: number; positions: Position[] } {
  return {
    cash: payload.cash_balance,
    positions: payload.positions.map((position) => ({
      ticker: position.ticker,
      quantity: position.quantity,
      avgCost: position.avg_cost
    }))
  };
}

export function Workstation() {
  const [quotes, setQuotes] = useState<Map<string, PriceQuote>>(new Map());
  const [watchlist, setWatchlist] = useState<string[]>(DEFAULT_TICKERS);
  const [selectedTicker, setSelectedTicker] = useState("AAPL");
  const [series, setSeries] = useState<Record<string, number[]>>({});
  const [cash, setCash] = useState(STARTING_CASH);
  const [positions, setPositions] = useState<Position[]>([]);
  const [snapshots, setSnapshots] = useState<PortfolioSnapshot[]>([{ timestamp: nowLabel(), totalValue: STARTING_CASH }]);
  const [status, setStatus] = useState<"connecting" | "connected" | "reconnecting" | "disconnected">("connecting");
  const [lastFlash, setLastFlash] = useState<Record<string, TradeSide | "flat">>({});
  const [tradeTicker, setTradeTicker] = useState("AAPL");
  const [quantity, setQuantity] = useState("1");
  const [watchTicker, setWatchTicker] = useState("");
  const [notice, setNotice] = useState("Market stream connecting.");
  const [chatInput, setChatInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [chatDisabled, setChatDisabled] = useState("AI chat is waiting for the backend /api/chat contract.");
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "system", content: "Manual trading is available. AI chat will activate when /api/chat is implemented and configured." }
  ]);
  const previousPrices = useRef<Map<string, number>>(new Map());

  useEffect(() => {
    getMarketPrices()
      .then((prices) => {
        setQuotes(quoteMap(prices));
        setSeries((current) => appendSeries(current, prices));
        setNotice("Loaded initial market snapshot.");
      })
      .catch((error: Error) => setNotice(error.message));

    getPortfolio()
      .then((payload) => {
        const next = mapPortfolio(payload);
        setCash(next.cash);
        setPositions(next.positions);
      })
      .catch(() => undefined);

    getHealth()
      .then((payload) => {
        if (payload.chat_enabled) {
          setChatDisabled("");
          setMessages([{ role: "system", content: "AI chat is ready." }]);
        } else {
          setChatDisabled("LLM API key is required, or enable LLM_MOCK=true.");
          setMessages([{ role: "system", content: "LLM API key is required, or enable LLM_MOCK=true." }]);
        }
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    const events = new EventSource("/api/stream/prices");
    setStatus("connecting");

    events.addEventListener("open", () => {
      setStatus("connected");
      setNotice("Live market stream connected.");
    });

    events.addEventListener("prices", (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as PriceStreamPayload;
      const prices = payload.prices ?? [];
      setStatus("connected");
      setQuotes((current) => {
        const next = new Map(current);
        const flashes: Record<string, TradeSide | "flat"> = {};
        prices.forEach((quote) => {
          const previous = previousPrices.current.get(quote.ticker) ?? current.get(quote.ticker)?.price;
          previousPrices.current.set(quote.ticker, quote.price);
          if (previous !== undefined && previous !== quote.price) {
            flashes[quote.ticker] = quote.price > previous ? "buy" : "sell";
          }
          next.set(quote.ticker, quote);
        });
        if (Object.keys(flashes).length > 0) {
          setLastFlash(flashes);
          window.setTimeout(() => setLastFlash({}), 520);
        }
        return next;
      });
      setSeries((current) => appendSeries(current, prices));
    });

    events.addEventListener("heartbeat", () => setStatus("connected"));
    events.onerror = () => setStatus((current) => (current === "connecting" ? "reconnecting" : "disconnected"));

    return () => events.close();
  }, []);

  const positionViews = useMemo(() => buildPositionViews(positions, quotes, cash), [positions, quotes, cash]);
  const totalValue = useMemo(() => portfolioTotal(cash, positionViews), [cash, positionViews]);
  const totalPnl = totalValue - STARTING_CASH;
  const selectedQuote = quotes.get(selectedTicker);
  const selectedSeries = series[selectedTicker] ?? (selectedQuote ? [selectedQuote.price] : []);

  useEffect(() => {
    const id = window.setInterval(() => {
      setSnapshots((current) => [...current.slice(-79), { timestamp: nowLabel(), totalValue }]);
    }, 3000);
    return () => window.clearInterval(id);
  }, [totalValue]);

  async function addTicker(event: FormEvent) {
    event.preventDefault();
    const ticker = normalizeTicker(watchTicker);
    if (!isTicker(ticker)) {
      setNotice("Ticker must be 1-5 uppercase letters.");
      return;
    }
    try {
      await addWatchlistTicker(ticker);
    } catch (error) {
      if (!(error instanceof EndpointUnavailableError)) {
        setNotice((error as Error).message);
        return;
      }
    }
    try {
      const quote = await getMarketPrice(ticker);
      setQuotes((current) => new Map(current).set(ticker, quote));
      setSeries((current) => appendSeries(current, [quote]));
    } catch {
      // The SSE stream will fill prices once the backend tracks this ticker.
    }
    setWatchlist((current) => (current.includes(ticker) ? current : [...current, ticker]));
    setSelectedTicker(ticker);
    setTradeTicker(ticker);
    setWatchTicker("");
    setNotice(`Added ${ticker} to the watchlist.`);
  }

  async function removeTicker(ticker: string) {
    try {
      await removeWatchlistTicker(ticker);
    } catch (error) {
      if (!(error instanceof EndpointUnavailableError)) {
        setNotice((error as Error).message);
        return;
      }
    }
    setWatchlist((current) => current.filter((symbol) => symbol !== ticker));
    if (selectedTicker === ticker) {
      setSelectedTicker(watchlist.find((symbol) => symbol !== ticker) ?? "AAPL");
    }
  }

  async function submitTrade(side: TradeSide) {
    const ticker = normalizeTicker(tradeTicker);
    const parsedQuantity = Number(quantity);
    if (!isTicker(ticker) || !Number.isFinite(parsedQuantity) || parsedQuantity <= 0) {
      setNotice("Enter a valid ticker and positive quantity.");
      return;
    }
    const quote = quotes.get(ticker) ?? (await getMarketPrice(ticker).catch(() => undefined));
    if (!quote) {
      setNotice(`No price available for ${ticker}.`);
      return;
    }

    try {
      const response = await executeTrade(ticker, parsedQuantity, side);
      if (response.portfolio) {
        const next = mapPortfolio(response.portfolio);
        setCash(next.cash);
        setPositions(next.positions);
      }
      setWatchlist((current) => (current.includes(ticker) ? current : [...current, ticker]));
      setNotice(`${side === "buy" ? "Bought" : "Sold"} ${formatNumber(parsedQuantity, 4)} ${ticker}; order executed.`);
    } catch (error) {
      if (!(error instanceof EndpointUnavailableError)) {
        setNotice((error as Error).message);
        return;
      }
      try {
        const next = applyLocalTrade(positions, cash, ticker, parsedQuantity, side, quote.price);
        setPositions(next.positions);
        setCash(next.cash);
        setWatchlist((current) => (current.includes(ticker) ? current : [...current, ticker]));
        setNotice(`${side.toUpperCase()} ${formatNumber(parsedQuantity, 4)} ${ticker} filled locally at ${formatCurrency(quote.price)}.`);
      } catch (localError) {
        setNotice((localError as Error).message);
      }
    }
  }

  async function submitChat(event: FormEvent) {
    event.preventDefault();
    if (chatDisabled || !chatInput.trim()) return;
    const prompt = chatInput.trim();
    setChatInput("");
    setChatBusy(true);
    setMessages((current) => [...current, { role: "user", content: prompt }]);
    try {
      const response = await sendChatMessage(prompt);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: response.message ?? "Received an AI response.",
          actions: response.actions?.map((action) => JSON.stringify(action))
        }
      ]);
      getPortfolio()
        .then((payload) => {
          const next = mapPortfolio(payload);
          setCash(next.cash);
          setPositions(next.positions);
        })
        .catch(() => undefined);
    } catch (error) {
      setChatDisabled((error as Error).message);
      setMessages((current) => [...current, { role: "system", content: (error as Error).message }]);
    } finally {
      setChatBusy(false);
    }
  }

  return (
    <main className="terminal" data-testid="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">FinAlly / AI trading workstation</p>
          <h1>Market Command</h1>
        </div>
        <div className="status-strip" aria-live="polite" data-testid="connection-status" data-state={status}>
          <span className={`status-dot ${status}`} />
          <span>{status}</span>
        </div>
        <div className="metric" data-testid="portfolio-summary">
          <span>Total equity</span>
          <strong data-testid="portfolio-total">{formatCurrency(totalValue)}</strong>
        </div>
        <div className="metric">
          <span>Cash</span>
          <strong data-testid="portfolio-cash">{formatCurrency(cash)}</strong>
        </div>
        <div className={`metric ${totalPnl >= 0 ? "positive" : "negative"}`}>
          <span>Open P&L</span>
          <strong>{formatCurrency(totalPnl)}</strong>
        </div>
      </header>

      <section className="ticker-tape" aria-label="Market tape">
        {watchlist.map((ticker) => {
          const quote = quotes.get(ticker);
          return (
            <button key={ticker} className={ticker === selectedTicker ? "active" : ""} onClick={() => setSelectedTicker(ticker)}>
              <b>{ticker}</b>
              <span>{quote ? formatCurrency(quote.price) : "--"}</span>
              <small className={quote && quote.change >= 0 ? "positive" : "negative"}>{quote ? formatPercent(quote.change_percent) : "waiting"}</small>
            </button>
          );
        })}
      </section>

      <div className="grid">
        <aside className="panel watchlist" data-testid="watchlist-panel">
          <div className="panel-header">
            <h2>Watchlist</h2>
            <form onSubmit={addTicker} className="inline-form">
              <input aria-label="Ticker to add" value={watchTicker} onChange={(event) => setWatchTicker(event.target.value)} placeholder="AMD" />
              <button type="submit">Add</button>
            </form>
          </div>
          <div className="watch-rows">
            {watchlist.map((ticker) => {
              const quote = quotes.get(ticker);
              const direction = lastFlash[ticker];
              return (
                <button
                  data-testid={`watchlist-row-${ticker}`}
                  className={`watch-row ${ticker === selectedTicker ? "selected" : ""} ${direction === "buy" ? "flash-up" : ""} ${direction === "sell" ? "flash-down" : ""}`}
                  key={ticker}
                  onClick={() => {
                    setSelectedTicker(ticker);
                    setTradeTicker(ticker);
                  }}
                >
                  <span className="symbol">{ticker}</span>
                  <span data-testid="watchlist-price">{quote ? formatCurrency(quote.price) : "--"}</span>
                  <span className={quote && quote.change >= 0 ? "positive" : "negative"}>{quote ? formatPercent(quote.change_percent) : "--"}</span>
                  <Sparkline points={series[ticker] ?? []} label={`${ticker} sparkline`} />
                  <span className="stale">{quote?.stale ? "stale" : quote?.session ?? "live"}</span>
                  <span className="remove" onClick={(event) => { event.stopPropagation(); void removeTicker(ticker); }}>x</span>
                </button>
              );
            })}
          </div>
        </aside>

        <section className="panel main-chart">
          <div className="panel-header">
            <div>
              <h2>{selectedTicker}</h2>
              <p>{selectedQuote?.source ?? "simulator"} / {selectedQuote?.timestamp ? new Date(selectedQuote.timestamp).toLocaleTimeString() : "waiting for ticks"}</p>
            </div>
            <strong className={selectedQuote && selectedQuote.change >= 0 ? "positive" : "negative"}>{selectedQuote ? formatCurrency(selectedQuote.price) : "--"}</strong>
          </div>
          <LineChart points={selectedSeries} title={`${selectedTicker} price path`} valueLabel={selectedQuote ? formatPercent(selectedQuote.change_percent) : undefined} />
        </section>

        <aside className="panel chat" data-testid="chat-panel" data-state={chatDisabled ? "disabled" : "ready"}>
          <div className="panel-header">
            <h2>AI Copilot</h2>
            <span className="badge">{chatDisabled ? "disabled" : "ready"}</span>
          </div>
          <div className="messages">
            {messages.map((message, index) => (
              <div key={`${message.role}-${index}`} className={`message ${message.role}`}>
                <span>{message.role}</span>
                <p data-testid={message.role === "assistant" ? "chat-message-assistant" : undefined}>{message.content}</p>
                {message.actions?.map((action) => <small data-testid="chat-action-result" key={action}>{action}</small>)}
              </div>
            ))}
          </div>
          {chatDisabled ? <p className="chat-disabled" data-testid="chat-disabled-message">{chatDisabled}</p> : null}
          <form className="chat-form" onSubmit={submitChat}>
            <input data-testid="chat-input" disabled={Boolean(chatDisabled) || chatBusy} value={chatInput} onChange={(event) => setChatInput(event.target.value)} placeholder={chatDisabled || "Ask about risk, P&L, or trades"} />
            <button data-testid="chat-send-button" disabled={Boolean(chatDisabled) || chatBusy} type="submit">{chatBusy ? "..." : "Send"}</button>
          </form>
        </aside>

        <section className="panel portfolio" data-testid="portfolio-heatmap">
          <div className="panel-header">
            <h2>Portfolio Heatmap</h2>
            <span>{positionViews.length} positions</span>
          </div>
          <Heatmap positions={positionViews} />
        </section>

        <section className="panel pnl" data-testid="portfolio-pnl-chart">
          <LineChart points={snapshots.map((snapshot) => snapshot.totalValue)} title="Portfolio value" valueLabel={formatCurrency(totalValue)} />
        </section>

        <section className="panel trade" data-testid="trade-bar">
          <div className="panel-header">
            <h2>Trade Bar</h2>
            <span data-testid="trade-status">{notice}</span>
          </div>
          <div className="trade-controls">
            <input data-testid="trade-ticker-input" aria-label="Trade ticker" value={tradeTicker} onChange={(event) => setTradeTicker(event.target.value)} />
            <input data-testid="trade-quantity-input" aria-label="Trade quantity" value={quantity} type="number" min="0" step="0.000001" onChange={(event) => setQuantity(event.target.value)} />
            <button data-testid="buy-button" className="buy" onClick={() => void submitTrade("buy")}>Buy</button>
            <button data-testid="sell-button" className="sell" onClick={() => void submitTrade("sell")}>Sell</button>
          </div>
        </section>

        <section className="panel positions" data-testid="positions-table">
          <div className="panel-header">
            <h2>Positions</h2>
            <span>Marked to live prices</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Qty</th>
                <th>Avg cost</th>
                <th>Last</th>
                <th>Unrealized</th>
                <th>Return</th>
              </tr>
            </thead>
            <tbody>
              {positionViews.length === 0 ? (
                <tr><td colSpan={6}>No open positions. Use the trade bar to simulate fills.</td></tr>
              ) : (
                positionViews.map((position) => (
                  <tr key={position.ticker} data-testid={`position-row-${position.ticker}`}>
                    <td>{position.ticker}</td>
                    <td data-testid="position-quantity">{formatNumber(position.quantity, 4)}</td>
                    <td>{formatCurrency(position.avgCost)}</td>
                    <td>{formatCurrency(position.currentPrice)}</td>
                    <td className={position.unrealizedPnl >= 0 ? "positive" : "negative"}>{formatCurrency(position.unrealizedPnl)}</td>
                    <td className={position.unrealizedReturn >= 0 ? "positive" : "negative"}>{formatPercent(position.unrealizedReturn)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </section>
      </div>
    </main>
  );
}

function appendSeries(current: Record<string, number[]>, prices: PriceQuote[]) {
  const next = { ...current };
  prices.forEach((quote) => {
    next[quote.ticker] = [...(next[quote.ticker] ?? []), quote.price].slice(-MAX_SERIES);
  });
  return next;
}
