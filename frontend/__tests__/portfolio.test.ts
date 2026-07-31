import { describe, expect, it } from "vitest";
import { applyLocalTrade, buildPositionViews, quoteMap, STARTING_CASH } from "@/lib/portfolio";
import type { PriceQuote } from "@/lib/types";

const quote = (ticker: string, price: number): PriceQuote => ({
  ticker,
  price,
  previous_price: price - 1,
  change: 1,
  change_percent: 0.5,
  direction: "up",
  stale: false,
  source: "simulator"
});

describe("portfolio helpers", () => {
  it("applies local buys with weighted average cost", () => {
    const first = applyLocalTrade([], STARTING_CASH, "AAPL", 10, "buy", 100);
    const second = applyLocalTrade(first.positions, first.cash, "AAPL", 5, "buy", 130);

    expect(second.cash).toBe(8350);
    expect(second.positions).toEqual([{ ticker: "AAPL", quantity: 15, avgCost: 110 }]);
  });

  it("rejects sells above held shares", () => {
    expect(() => applyLocalTrade([{ ticker: "MSFT", quantity: 2, avgCost: 300 }], 100, "MSFT", 3, "sell", 305)).toThrow(
      "Insufficient shares"
    );
  });

  it("builds marked-to-market position views", () => {
    const views = buildPositionViews(
      [{ ticker: "NVDA", quantity: 4, avgCost: 900 }],
      quoteMap([quote("NVDA", 1000)]),
      1000
    );

    expect(views[0].marketValue).toBe(4000);
    expect(views[0].unrealizedPnl).toBe(400);
    expect(views[0].unrealizedReturn).toBeCloseTo(11.111, 3);
    expect(views[0].weight).toBe(80);
  });
});
