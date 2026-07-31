"""Portfolio and watchlist service boundary."""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from app.core.errors import ApiError
from app.db import repository as db_repository
from app.db.repository import DatabaseValidationError, TradeExecutionError
from app.llm.models import (
    ChatMessageRecord,
    ChatRole,
    PortfolioContext,
    PositionContext,
    TradeSide,
    WatchlistAction,
    WatchlistQuoteContext,
)
from app.market.serialization import quote_to_payload, utc_iso
from app.market.service import DEFAULT_WATCHLIST_TICKERS, MarketDataService
from app.market.validation import is_valid_ticker, normalize_ticker

DEFAULT_USER_ID = "default"
MAX_HISTORY_LIMIT = 2_000


@dataclass(slots=True)
class Position:
    ticker: str
    quantity: float
    avg_cost: float
    updated_at: str


class InMemoryFinAllyRepository:
    """Temporary repository with the same shape expected from the DB layer."""

    def __init__(self) -> None:
        now = utc_iso(datetime.now(timezone.utc))
        self._lock = asyncio.Lock()
        self.cash_balance = 10_000.0
        self.watchlist = set(DEFAULT_WATCHLIST_TICKERS)
        self.positions: dict[str, Position] = {}
        self.trades: list[dict] = []
        self.snapshots: list[dict] = [
            {
                "id": str(uuid4()),
                "user_id": DEFAULT_USER_ID,
                "total_value": 10_000.0,
                "recorded_at": now,
            }
        ]
        self.chat_messages: list[dict] = []

    async def tracked_tickers(self) -> set[str]:
        async with self._lock:
            return set(self.watchlist) | set(self.positions)

    async def get_watchlist(self) -> list[str]:
        async with self._lock:
            return sorted(self.watchlist)

    async def add_watchlist_ticker(self, ticker: str) -> bool:
        async with self._lock:
            before = len(self.watchlist)
            self.watchlist.add(ticker)
            return len(self.watchlist) > before

    async def remove_watchlist_ticker(self, ticker: str) -> bool:
        async with self._lock:
            if ticker not in self.watchlist:
                return False
            self.watchlist.remove(ticker)
            return True

    async def state(self) -> tuple[float, dict[str, Position]]:
        async with self._lock:
            return self.cash_balance, dict(self.positions)

    async def record_snapshot(self, total_value: float) -> dict:
        snapshot = {
            "id": str(uuid4()),
            "user_id": DEFAULT_USER_ID,
            "total_value": round(total_value, 2),
            "recorded_at": utc_iso(datetime.now(timezone.utc)),
        }
        async with self._lock:
            self.snapshots.append(snapshot)
            self.snapshots = self.snapshots[-MAX_HISTORY_LIMIT:]
        return snapshot

    async def history(self, limit: int) -> list[dict]:
        async with self._lock:
            return list(self.snapshots[-limit:])

    async def apply_trade(self, ticker: str, side: str, quantity: float, price: float) -> dict:
        async with self._lock:
            cash_before = self.cash_balance
            position = self.positions.get(ticker)
            notional = quantity * price

            if side == "buy":
                if notional > self.cash_balance + 1e-9:
                    raise ApiError(
                        400,
                        "INSUFFICIENT_CASH",
                        f"Not enough cash to buy {quantity:g} shares of {ticker}.",
                        {
                            "ticker": ticker,
                            "required_cash": round(notional, 2),
                            "available_cash": round(self.cash_balance, 2),
                        },
                    )
                if position is None:
                    position = Position(ticker, quantity, price, utc_iso(datetime.now(timezone.utc)))
                else:
                    new_quantity = position.quantity + quantity
                    new_avg_cost = (
                        (position.quantity * position.avg_cost) + notional
                    ) / new_quantity
                    position = Position(
                        ticker,
                        new_quantity,
                        new_avg_cost,
                        utc_iso(datetime.now(timezone.utc)),
                    )
                self.cash_balance -= notional
                self.positions[ticker] = position
            else:
                if position is None or quantity > position.quantity + 1e-9:
                    raise ApiError(
                        400,
                        "INSUFFICIENT_SHARES",
                        f"Not enough shares to sell {quantity:g} shares of {ticker}.",
                        {
                            "ticker": ticker,
                            "requested_quantity": quantity,
                            "available_quantity": position.quantity if position else 0.0,
                        },
                    )
                remaining = position.quantity - quantity
                self.cash_balance += notional
                if remaining <= 1e-9:
                    self.positions.pop(ticker, None)
                    position = None
                else:
                    position = Position(
                        ticker,
                        remaining,
                        position.avg_cost,
                        utc_iso(datetime.now(timezone.utc)),
                    )
                    self.positions[ticker] = position

            added_to_watchlist = ticker not in self.watchlist
            self.watchlist.add(ticker)
            trade = {
                "id": str(uuid4()),
                "user_id": DEFAULT_USER_ID,
                "ticker": ticker,
                "side": side,
                "quantity": quantity,
                "price": round(price, 4),
                "notional": round(notional, 2),
                "cash_before": round(cash_before, 2),
                "cash_after": round(self.cash_balance, 2),
                "executed_at": utc_iso(datetime.now(timezone.utc)),
            }
            self.trades.append(trade)
            return {
                "trade": trade,
                "cash_balance": self.cash_balance,
                "position": position,
                "added_to_watchlist": added_to_watchlist,
            }

    async def add_chat_message(
        self,
        role: str,
        content: str,
        actions: list[dict] | None = None,
    ) -> dict:
        message = {
            "id": str(uuid4()),
            "user_id": DEFAULT_USER_ID,
            "role": role,
            "content": content,
            "actions": actions,
            "created_at": utc_iso(datetime.now(timezone.utc)),
        }
        async with self._lock:
            self.chat_messages.append(message)
        return message

    async def recent_messages(self, user_id: str, limit: int = 20) -> list[ChatMessageRecord]:
        async with self._lock:
            messages = [
                item for item in self.chat_messages if item.get("user_id", DEFAULT_USER_ID) == user_id
            ][-limit:]
        return [
            ChatMessageRecord(
                id=item["id"],
                user_id=item.get("user_id", DEFAULT_USER_ID),
                role=ChatRole(item["role"]),
                content=item["content"],
                actions=item.get("actions"),
                created_at=item.get("created_at"),
            )
            for item in messages
        ]

    async def save_message(
        self,
        user_id: str,
        role: str,
        content: str,
        actions: list[dict] | None = None,
    ) -> ChatMessageRecord:
        saved = await self.add_chat_message(role=role, content=content, actions=actions)
        saved["user_id"] = user_id
        return ChatMessageRecord(
            id=saved["id"],
            user_id=user_id,
            role=ChatRole(role),
            content=content,
            actions=actions,
            created_at=saved["created_at"],
        )


def db_error_to_api_error(exc: DatabaseValidationError) -> ApiError:
    status_code = 400
    if exc.code in {"USER_NOT_FOUND"}:
        status_code = 404
    return ApiError(status_code, exc.code, exc.message, exc.details)


class SQLiteFinAllyRepository:
    """Async adapter for the SQLite repository functions."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    async def tracked_tickers(self) -> set[str]:
        watchlist = await asyncio.to_thread(db_repository.get_watchlist, db_path=self.db_path)
        positions = await asyncio.to_thread(db_repository.get_positions, db_path=self.db_path)
        return set(watchlist) | {row["ticker"] for row in positions}

    async def get_watchlist(self) -> list[str]:
        return await asyncio.to_thread(db_repository.get_watchlist, db_path=self.db_path)

    async def add_watchlist_ticker(self, ticker: str) -> bool:
        try:
            result = await asyncio.to_thread(
                db_repository.add_watchlist_ticker,
                ticker,
                db_path=self.db_path,
            )
        except DatabaseValidationError as exc:
            raise db_error_to_api_error(exc) from exc
        return bool(result["added"])

    async def remove_watchlist_ticker(self, ticker: str) -> bool:
        try:
            result = await asyncio.to_thread(
                db_repository.remove_watchlist_ticker,
                ticker,
                db_path=self.db_path,
            )
        except DatabaseValidationError as exc:
            raise db_error_to_api_error(exc) from exc
        return bool(result["removed"])

    async def state(self) -> tuple[float, dict[str, Position]]:
        profile = await asyncio.to_thread(db_repository.get_user_profile, db_path=self.db_path)
        position_rows = await asyncio.to_thread(db_repository.get_positions, db_path=self.db_path)
        positions = {
            row["ticker"]: Position(
                ticker=row["ticker"],
                quantity=float(row["quantity"]),
                avg_cost=float(row["avg_cost"]),
                updated_at=row["updated_at"],
            )
            for row in position_rows
        }
        return float(profile["cash_balance"]), positions

    async def record_snapshot(self, total_value: float) -> dict:
        try:
            return await asyncio.to_thread(
                db_repository.record_portfolio_snapshot,
                total_value,
                db_path=self.db_path,
            )
        except DatabaseValidationError as exc:
            raise db_error_to_api_error(exc) from exc

    async def history(self, limit: int) -> list[dict]:
        return await asyncio.to_thread(
            db_repository.get_portfolio_snapshots,
            limit=limit,
            db_path=self.db_path,
        )

    async def apply_trade(self, ticker: str, side: str, quantity: float, price: float) -> dict:
        try:
            result = await asyncio.to_thread(
                db_repository.execute_trade,
                ticker=ticker,
                side=side,
                quantity=quantity,
                price=price,
                db_path=self.db_path,
            )
        except TradeExecutionError as exc:
            raise db_error_to_api_error(exc) from exc
        except DatabaseValidationError as exc:
            raise db_error_to_api_error(exc) from exc

        position = result["position"]
        return {
            **result,
            "position": None
            if position is None
            else Position(
                ticker=position["ticker"],
                quantity=float(position["quantity"]),
                avg_cost=float(position["avg_cost"]),
                updated_at=position["updated_at"],
            ),
        }

    async def recent_messages(self, user_id: str, limit: int = 20) -> list[ChatMessageRecord]:
        rows = await asyncio.to_thread(
            db_repository.get_chat_messages,
            user_id,
            limit=limit,
            db_path=self.db_path,
        )
        return [
            ChatMessageRecord(
                id=row["id"],
                user_id=row["user_id"],
                role=ChatRole(row["role"]),
                content=row["content"],
                actions=row.get("actions"),
                created_at=row.get("created_at"),
            )
            for row in rows
        ]

    async def save_message(
        self,
        user_id: str,
        role: str,
        content: str,
        actions: list[dict] | None = None,
    ) -> ChatMessageRecord:
        try:
            row = await asyncio.to_thread(
                db_repository.add_chat_message,
                role=role,
                content=content,
                actions=actions,
                user_id=user_id,
                db_path=self.db_path,
            )
        except DatabaseValidationError as exc:
            raise db_error_to_api_error(exc) from exc
        return ChatMessageRecord(
            id=row["id"],
            user_id=row["user_id"],
            role=ChatRole(row["role"]),
            content=row["content"],
            actions=row.get("actions"),
            created_at=row.get("created_at"),
        )


def normalize_valid_ticker(ticker: str) -> str:
    symbol = normalize_ticker(ticker)
    if not is_valid_ticker(symbol):
        raise ApiError(
            400,
            "INVALID_TICKER",
            "Ticker must be 1-5 uppercase letters.",
            {"ticker": ticker},
        )
    return symbol


def validate_side(side: str) -> str:
    normalized = side.strip().lower()
    if normalized not in {"buy", "sell"}:
        raise ApiError(
            400,
            "INVALID_TRADE_SIDE",
            "Trade side must be buy or sell.",
            {"side": side},
        )
    return normalized


def validate_quantity(quantity: float) -> float:
    if not math.isfinite(quantity) or quantity <= 0:
        raise ApiError(400, "INVALID_QUANTITY", "Quantity must be a positive number.")
    try:
        decimal = Decimal(str(quantity))
    except InvalidOperation as exc:
        raise ApiError(400, "INVALID_QUANTITY", "Quantity must be numeric.") from exc
    if decimal.as_tuple().exponent < -6:
        raise ApiError(
            400,
            "INVALID_QUANTITY_PRECISION",
            "Quantity supports up to 6 decimal places.",
            {"quantity": quantity},
        )
    return float(decimal)


class PortfolioService:
    def __init__(
        self,
        repository: InMemoryFinAllyRepository,
        market_service: MarketDataService,
    ) -> None:
        self.repository = repository
        self.market_service = market_service

    async def ensure_price(self, ticker: str) -> dict:
        quote = await self.market_service.cache.get(ticker)
        if quote is None:
            await self.market_service.add_tracked_ticker(ticker)
            await self.market_service.refresh_once()
            quote = await self.market_service.cache.get(ticker)
        if quote is None:
            raise ApiError(
                404,
                "MARKET_DATA_UNAVAILABLE",
                "Market data is not available for this ticker.",
                {"ticker": ticker},
            )
        return quote_to_payload(quote)

    async def portfolio(self, record_snapshot: bool = False) -> dict:
        cash_balance, positions = await self.repository.state()
        rows = []
        positions_value = 0.0
        for ticker, position in sorted(positions.items()):
            price = (await self.ensure_price(ticker))["price"]
            market_value = position.quantity * price
            unrealized_pnl = market_value - (position.quantity * position.avg_cost)
            unrealized_return_percent = (
                (price - position.avg_cost) / position.avg_cost * 100
                if position.avg_cost
                else 0.0
            )
            positions_value += market_value
            rows.append(
                {
                    "ticker": ticker,
                    "quantity": round(position.quantity, 6),
                    "avg_cost": round(position.avg_cost, 4),
                    "current_price": round(price, 4),
                    "market_value": round(market_value, 2),
                    "unrealized_pnl": round(unrealized_pnl, 2),
                    "unrealized_return_percent": round(unrealized_return_percent, 4),
                }
            )
        total_value = cash_balance + positions_value
        if record_snapshot:
            snapshot = await self.repository.record_snapshot(total_value)
            recorded_at = snapshot["recorded_at"]
        else:
            recorded_at = utc_iso(datetime.now(timezone.utc))
        return {
            "cash_balance": round(cash_balance, 2),
            "total_value": round(total_value, 2),
            "positions": rows,
            "recorded_at": recorded_at,
        }

    async def trade(self, ticker: str, side: str, quantity: float) -> dict:
        symbol = normalize_valid_ticker(ticker)
        trade_side = validate_side(side)
        trade_quantity = validate_quantity(quantity)
        quote = await self.ensure_price(symbol)
        result = await self.repository.apply_trade(
            symbol,
            trade_side,
            trade_quantity,
            quote["price"],
        )
        await self.market_service.add_tracked_ticker(symbol)
        portfolio = await self.portfolio(record_snapshot=True)
        position = result["position"]
        return {
            "trade": result["trade"],
            "cash_balance": round(result["cash_balance"], 2),
            "position": None
            if position is None
            else {
                "ticker": position.ticker,
                "quantity": round(position.quantity, 6),
                "avg_cost": round(position.avg_cost, 4),
                "updated_at": position.updated_at,
            },
            "portfolio": portfolio,
            "added_to_watchlist": result["added_to_watchlist"],
        }

    async def history(self, limit: int = 200) -> dict:
        bounded_limit = min(max(limit, 1), MAX_HISTORY_LIMIT)
        return {"history": await self.repository.history(bounded_limit), "limit": bounded_limit}

    async def get_portfolio_context(self, user_id: str) -> PortfolioContext:
        portfolio = await self.portfolio()
        tickers = await self.repository.get_watchlist()
        watchlist = []
        for ticker in tickers:
            price = await self.ensure_price(ticker)
            watchlist.append(
                WatchlistQuoteContext(
                    ticker=ticker,
                    price=price.get("price"),
                    change_percent=price.get("change_percent"),
                    stale=price.get("stale", False),
                    source=price.get("source"),
                )
            )
        return PortfolioContext(
            user_id=user_id,
            cash_balance=portfolio["cash_balance"],
            total_value=portfolio["total_value"],
            positions=[
                PositionContext(
                    ticker=position["ticker"],
                    quantity=position["quantity"],
                    avg_cost=position["avg_cost"],
                    current_price=position["current_price"],
                    market_value=position["market_value"],
                    unrealized_pnl=position["unrealized_pnl"],
                    unrealized_return_percent=position["unrealized_return_percent"],
                )
                for position in portfolio["positions"]
            ],
            watchlist=watchlist,
        )

    async def execute_trade(
        self,
        user_id: str,
        ticker: str,
        side: TradeSide,
        quantity: float,
        source: str = "ai",
    ) -> dict:
        result = await self.trade(ticker=ticker, side=side.value, quantity=quantity)
        result["source"] = source
        result["user_id"] = user_id
        return result


class WatchlistService:
    def __init__(
        self,
        repository: InMemoryFinAllyRepository,
        portfolio_service: PortfolioService,
    ) -> None:
        self.repository = repository
        self.portfolio_service = portfolio_service

    async def watchlist(self) -> dict:
        tickers = await self.repository.get_watchlist()
        items = []
        for ticker in tickers:
            try:
                price = await self.portfolio_service.ensure_price(ticker)
            except ApiError:
                price = None
            items.append({"ticker": ticker, "price": price})
        return {"tickers": tickers, "items": items}

    async def add(self, ticker: str) -> dict:
        symbol = normalize_valid_ticker(ticker)
        added = await self.repository.add_watchlist_ticker(symbol)
        await self.portfolio_service.market_service.add_tracked_ticker(symbol)
        price = await self.portfolio_service.ensure_price(symbol)
        return {"ticker": symbol, "added": added, "item": {"ticker": symbol, "price": price}}

    async def remove(self, ticker: str) -> dict:
        symbol = normalize_valid_ticker(ticker)
        removed = await self.repository.remove_watchlist_ticker(symbol)
        if not removed:
            raise ApiError(
                404,
                "WATCHLIST_TICKER_NOT_FOUND",
                "Ticker is not in the watchlist.",
                {"ticker": symbol},
            )
        return {"ticker": symbol, "removed": True}

    async def change_watchlist(
        self,
        user_id: str,
        ticker: str,
        action: WatchlistAction,
        source: str = "ai",
    ) -> dict:
        result = (
            await self.add(ticker)
            if action == WatchlistAction.ADD
            else await self.remove(ticker)
        )
        result["source"] = source
        result["user_id"] = user_id
        result["action"] = action.value
        return result
