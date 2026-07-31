"""Shared request and response schemas for the public API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TickerRequest(BaseModel):
    ticker: str


class TradeRequest(BaseModel):
    ticker: str
    side: str
    quantity: float = Field(gt=0)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


class PositionResponse(BaseModel):
    ticker: str
    quantity: float
    avg_cost: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_return_percent: float


class PortfolioResponse(BaseModel):
    cash_balance: float
    total_value: float
    positions: list[PositionResponse]
    recorded_at: str


class TradeResponse(BaseModel):
    trade: dict
    cash_balance: float
    position: dict | None
    portfolio: PortfolioResponse
    added_to_watchlist: bool


class WatchlistItemResponse(BaseModel):
    ticker: str
    price: dict | None = None


class WatchlistResponse(BaseModel):
    tickers: list[str]
    items: list[WatchlistItemResponse]


class PortfolioHistoryResponse(BaseModel):
    history: list[dict]
    limit: int


class ChatResponse(BaseModel):
    message: str
    actions: list[dict]
    created_at: str
    mock: bool = False
