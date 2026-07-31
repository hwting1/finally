import type { Position, PositionView, PriceQuote, TradeSide } from "./types";

export const STARTING_CASH = 10000;

export function quoteMap(quotes: PriceQuote[]): Map<string, PriceQuote> {
  return new Map(quotes.map((quote) => [quote.ticker, quote]));
}

export function buildPositionViews(
  positions: Position[],
  prices: Map<string, PriceQuote>,
  cash: number
): PositionView[] {
  const raw = positions
    .map((position) => {
      const currentPrice = prices.get(position.ticker)?.price ?? position.avgCost;
      const marketValue = position.quantity * currentPrice;
      const costBasis = position.quantity * position.avgCost;
      const unrealizedPnl = marketValue - costBasis;
      const unrealizedReturn = costBasis === 0 ? 0 : (unrealizedPnl / costBasis) * 100;
      return {
        ...position,
        currentPrice,
        marketValue,
        unrealizedPnl,
        unrealizedReturn,
        weight: 0
      };
    })
    .filter((position) => position.quantity > 0);

  const totalValue = portfolioTotal(cash, raw);
  return raw.map((position) => ({
    ...position,
    weight: totalValue === 0 ? 0 : (position.marketValue / totalValue) * 100
  }));
}

export function portfolioTotal(cash: number, positions: Pick<PositionView, "marketValue">[]): number {
  return cash + positions.reduce((sum, position) => sum + position.marketValue, 0);
}

export function applyLocalTrade(
  positions: Position[],
  cash: number,
  ticker: string,
  quantity: number,
  side: TradeSide,
  price: number
): { positions: Position[]; cash: number } {
  if (!Number.isFinite(quantity) || quantity <= 0 || !Number.isFinite(price) || price <= 0) {
    throw new Error("Enter a valid positive quantity.");
  }

  const existing = positions.find((position) => position.ticker === ticker);
  const notional = quantity * price;

  if (side === "buy") {
    if (notional > cash) {
      throw new Error("Insufficient cash for this order.");
    }
    if (!existing) {
      return { cash: cash - notional, positions: [...positions, { ticker, quantity, avgCost: price }] };
    }
    const nextQuantity = existing.quantity + quantity;
    const nextCost = (existing.avgCost * existing.quantity + notional) / nextQuantity;
    return {
      cash: cash - notional,
      positions: positions.map((position) =>
        position.ticker === ticker ? { ...position, quantity: nextQuantity, avgCost: nextCost } : position
      )
    };
  }

  if (!existing || existing.quantity < quantity) {
    throw new Error("Insufficient shares for this order.");
  }

  const nextQuantity = existing.quantity - quantity;
  return {
    cash: cash + notional,
    positions:
      nextQuantity <= 0.000001
        ? positions.filter((position) => position.ticker !== ticker)
        : positions.map((position) =>
            position.ticker === ticker ? { ...position, quantity: nextQuantity } : position
          )
  };
}
