export type Direction = "up" | "down" | "flat";

export type PriceQuote = {
  ticker: string;
  price: number;
  previous_price: number | null;
  previous_close?: number | null;
  change: number;
  change_percent: number;
  direction: Direction;
  timestamp?: string | null;
  stale: boolean;
  source: string;
  session?: string;
  volume?: number | null;
  day_open?: number | null;
  day_high?: number | null;
  day_low?: number | null;
};

export type PriceStreamPayload = {
  type: "prices" | "heartbeat";
  timestamp: string;
  prices?: PriceQuote[];
};

export type Position = {
  ticker: string;
  quantity: number;
  avgCost: number;
};

export type ApiPosition = {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_return_percent: number;
};

export type PortfolioResponse = {
  cash_balance: number;
  total_value: number;
  positions: ApiPosition[];
  recorded_at: string;
};

export type PositionView = Position & {
  currentPrice: number;
  marketValue: number;
  unrealizedPnl: number;
  unrealizedReturn: number;
  weight: number;
};

export type PortfolioSnapshot = {
  timestamp: string;
  totalValue: number;
};

export type ChatMessage = {
  role: "user" | "assistant" | "system";
  content: string;
  actions?: string[];
};

export type TradeSide = "buy" | "sell";
