"""Schemas for FinAlly LLM chat and AI action execution."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.market.validation import is_valid_ticker, normalize_ticker


DEFAULT_USER_ID = "default"


class ChatRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class TradeSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class WatchlistAction(StrEnum):
    ADD = "add"
    REMOVE = "remove"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    user_id: str = DEFAULT_USER_ID


class LLMTradeAction(BaseModel):
    ticker: str
    side: TradeSide
    quantity: float

    @field_validator("ticker")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return normalize_ticker(value)


class LLMWatchlistChange(BaseModel):
    ticker: str
    action: WatchlistAction

    @field_validator("ticker")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return normalize_ticker(value)


class LLMChatPlan(BaseModel):
    message: str = Field(min_length=1)
    trades: list[LLMTradeAction] = Field(default_factory=list)
    watchlist_changes: list[LLMWatchlistChange] = Field(default_factory=list)


class PositionContext(BaseModel):
    ticker: str
    quantity: float
    avg_cost: float | None = None
    current_price: float | None = None
    market_value: float | None = None
    unrealized_pnl: float | None = None
    unrealized_return_percent: float | None = None


class WatchlistQuoteContext(BaseModel):
    ticker: str
    price: float | None = None
    change_percent: float | None = None
    stale: bool = False
    source: str | None = None


class PortfolioContext(BaseModel):
    user_id: str = DEFAULT_USER_ID
    cash_balance: float = 0.0
    total_value: float = 0.0
    positions: list[PositionContext] = Field(default_factory=list)
    watchlist: list[WatchlistQuoteContext] = Field(default_factory=list)

    def price_for(self, ticker: str) -> float | None:
        symbol = normalize_ticker(ticker)
        for position in self.positions:
            if normalize_ticker(position.ticker) == symbol and position.current_price:
                return position.current_price
        for quote in self.watchlist:
            if normalize_ticker(quote.ticker) == symbol and quote.price:
                return quote.price
        return None


class ChatMessageRecord(BaseModel):
    id: str | None = None
    user_id: str = DEFAULT_USER_ID
    role: ChatRole
    content: str
    actions: list[dict[str, Any]] | None = None
    created_at: datetime | None = None


class ActionResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["trade", "watchlist"]
    requested: dict[str, Any]
    status: Literal["executed", "rejected", "failed"]
    code: str
    message: str
    timestamp: datetime
    result: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    message: str
    actions: list[ActionResult] = Field(default_factory=list)
    chat_enabled: bool = True


def quantity_has_valid_precision(quantity: float) -> bool:
    text = f"{quantity:.12f}".rstrip("0").rstrip(".")
    return "." not in text or len(text.split(".", 1)[1]) <= 6


def is_valid_trade_action(action: LLMTradeAction) -> bool:
    return is_valid_ticker(action.ticker) and action.quantity > 0 and quantity_has_valid_precision(
        action.quantity
    )
