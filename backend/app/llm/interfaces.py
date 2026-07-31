"""Service interfaces the LLM layer uses for persistence and mutations."""

from __future__ import annotations

from typing import Any, Protocol

from app.llm.models import ChatMessageRecord, PortfolioContext, TradeSide, WatchlistAction


class ChatHistoryStore(Protocol):
    async def recent_messages(self, user_id: str, limit: int = 20) -> list[ChatMessageRecord]:
        """Load recent chat history in ascending chronological order."""

    async def save_message(
        self,
        user_id: str,
        role: str,
        content: str,
        actions: list[dict[str, Any]] | None = None,
    ) -> ChatMessageRecord:
        """Persist one chat message and optional action audit details."""


class PortfolioContextReader(Protocol):
    async def get_portfolio_context(self, user_id: str) -> PortfolioContext:
        """Return current cash, positions, watchlist quotes, and total portfolio value."""


class TradeExecutor(Protocol):
    async def execute_trade(
        self,
        user_id: str,
        ticker: str,
        side: TradeSide,
        quantity: float,
        source: str = "ai",
    ) -> dict[str, Any]:
        """Execute a market trade using the same validation path as manual trades."""


class WatchlistExecutor(Protocol):
    async def change_watchlist(
        self,
        user_id: str,
        ticker: str,
        action: WatchlistAction,
        source: str = "ai",
    ) -> dict[str, Any]:
        """Add or remove a ticker using the backend watchlist service."""
