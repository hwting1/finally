import type { PortfolioResponse, PriceQuote, TradeSide } from "./types";

type ApiError = {
  error?: {
    code?: string;
    message?: string;
  };
  detail?: {
    code?: string;
    message?: string;
  };
};

export class EndpointUnavailableError extends Error {
  constructor(path: string) {
    super(`${path} is not available yet.`);
    this.name = "EndpointUnavailableError";
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...init?.headers
    }
  });

  if (response.status === 404 || response.status === 405) {
    throw new EndpointUnavailableError(path);
  }

  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ApiError;
    throw new Error(payload.error?.message ?? payload.detail?.message ?? payload.error?.code ?? payload.detail?.code ?? response.statusText);
  }

  return (await response.json()) as T;
}

export async function getMarketPrices(): Promise<PriceQuote[]> {
  const payload = await requestJson<{ prices: PriceQuote[] }>("/api/market/prices");
  return payload.prices;
}

export async function getMarketPrice(ticker: string): Promise<PriceQuote> {
  const payload = await requestJson<{ price: PriceQuote }>(`/api/market/prices/${ticker}`);
  return payload.price;
}

export async function getHealth(): Promise<{ ok: boolean; chat_enabled?: boolean }> {
  return requestJson("/api/health");
}

export async function getPortfolio(): Promise<PortfolioResponse> {
  return requestJson("/api/portfolio");
}

export async function executeTrade(ticker: string, quantity: number, side: TradeSide): Promise<{ portfolio?: PortfolioResponse }> {
  return requestJson("/api/portfolio/trade", {
    method: "POST",
    body: JSON.stringify({ ticker, quantity, side })
  });
}

export async function addWatchlistTicker(ticker: string): Promise<unknown> {
  return requestJson("/api/watchlist", {
    method: "POST",
    body: JSON.stringify({ ticker })
  });
}

export async function removeWatchlistTicker(ticker: string): Promise<unknown> {
  return requestJson(`/api/watchlist/${ticker}`, {
    method: "DELETE"
  });
}

export async function sendChatMessage(message: string): Promise<{ message?: string; actions?: unknown[] }> {
  return requestJson("/api/chat", {
    method: "POST",
    body: JSON.stringify({ message })
  });
}
