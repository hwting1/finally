import { describe, expect, it } from "vitest";
import { applyLocalTrade, buildPositionViews, portfolioTotal, quoteMap, STARTING_CASH } from "../lib/portfolio";
import type { PriceQuote } from "../lib/types";

function quote(ticker: string, price: number): PriceQuote {
  return {
    ticker,
    price,
    previous_price: price,
    previous_close: price,
    change: 0,
    change_percent: 0,
    direction: "flat",
    timestamp: new Date().toISOString(),
    stale: false,
    source: "simulator",
    session: "open"
  };
}

describe("portfolio helpers", () => {
  it("buys shares and lowers cash", () => {
    const result = applyLocalTrade([], STARTING_CASH, "AAPL", 5, "buy", 100);

    expect(result.cash).toBe(9500);
    expect(result.positions).toEqual([{ ticker: "AAPL", quantity: 5, avgCost: 100 }]);
  });

  it("sells shares and preserves average cost", () => {
    const result = applyLocalTrade([{ ticker: "AAPL", quantity: 5, avgCost: 90 }], 1000, "AAPL", 2, "sell", 100);

    expect(result.cash).toBe(1200);
    expect(result.positions).toEqual([{ ticker: "AAPL", quantity: 3, avgCost: 90 }]);
  });

  it("marks positions against live quotes", () => {
    const quotes = quoteMap([quote("AAPL", 110)]);
    const views = buildPositionViews([{ ticker: "AAPL", quantity: 2, avgCost: 100 }], quotes, 500);

    expect(views[0].unrealizedPnl).toBe(20);
    expect(portfolioTotal(500, views)).toBe(720);
  });
});
