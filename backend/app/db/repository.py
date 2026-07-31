"""Repository and service functions for FinAlly SQLite state."""

from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.db.connection import connect
from app.db.schema import DEFAULT_USER_ID, initialize_connection, utc_now_iso
from app.market.validation import is_valid_ticker, normalize_ticker

DEFAULT_SNAPSHOT_LIMIT = 2_000
MAX_QUANTITY_DECIMAL_PLACES = 6


class DatabaseValidationError(ValueError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class TradeExecutionError(DatabaseValidationError):
    pass


@dataclass(frozen=True, slots=True)
class TradeResult:
    trade: dict[str, Any]
    cash_balance: float
    position: dict[str, Any] | None
    portfolio_total: float
    added_to_watchlist: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "trade": self.trade,
            "cash_balance": self.cash_balance,
            "position": self.position,
            "portfolio_total": self.portfolio_total,
            "added_to_watchlist": self.added_to_watchlist,
        }


def validate_ticker(ticker: str) -> str:
    symbol = normalize_ticker(ticker)
    if not is_valid_ticker(symbol):
        raise DatabaseValidationError(
            "INVALID_TICKER",
            "Ticker must be 1 to 5 uppercase letters after normalization.",
            {"ticker": ticker},
        )
    return symbol


def validate_quantity(quantity: Any) -> float:
    if isinstance(quantity, bool):
        raise DatabaseValidationError("INVALID_QUANTITY", "Quantity must be numeric.")
    try:
        decimal_quantity = Decimal(str(quantity))
    except (InvalidOperation, ValueError):
        raise DatabaseValidationError("INVALID_QUANTITY", "Quantity must be numeric.") from None
    if not decimal_quantity.is_finite() or decimal_quantity <= 0:
        raise DatabaseValidationError("INVALID_QUANTITY", "Quantity must be greater than zero.")
    if abs(decimal_quantity.as_tuple().exponent) > MAX_QUANTITY_DECIMAL_PLACES:
        raise DatabaseValidationError(
            "QUANTITY_PRECISION_EXCEEDED",
            "Quantity supports at most 6 decimal places.",
            {"quantity": str(quantity), "max_decimal_places": MAX_QUANTITY_DECIMAL_PLACES},
        )
    return float(decimal_quantity)


def _validate_price(price: Any) -> float:
    try:
        numeric_price = float(price)
    except (TypeError, ValueError):
        raise DatabaseValidationError("INVALID_PRICE", "Price must be numeric.") from None
    if not math.isfinite(numeric_price) or numeric_price <= 0:
        raise DatabaseValidationError("INVALID_PRICE", "Price must be greater than zero.")
    return numeric_price


@contextmanager
def db_session(
    db_path: str | Path | None = None, connection: sqlite3.Connection | None = None
) -> Iterator[sqlite3.Connection]:
    if connection is not None:
        initialize_connection(connection)
        yield connection
        return
    with connect(db_path) as owned_connection:
        initialize_connection(owned_connection)
        yield owned_connection


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def get_user_profile(
    user_id: str = DEFAULT_USER_ID,
    *,
    db_path: str | Path | None = None,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    with db_session(db_path, connection) as conn:
        row = conn.execute("SELECT * FROM users_profile WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            raise DatabaseValidationError(
                "USER_NOT_FOUND", f"User profile '{user_id}' does not exist."
            )
        return dict(row)


def get_cash_balance(
    user_id: str = DEFAULT_USER_ID,
    *,
    db_path: str | Path | None = None,
    connection: sqlite3.Connection | None = None,
) -> float:
    return float(get_user_profile(user_id, db_path=db_path, connection=connection)["cash_balance"])


def get_watchlist(
    user_id: str = DEFAULT_USER_ID,
    *,
    db_path: str | Path | None = None,
    connection: sqlite3.Connection | None = None,
) -> list[str]:
    with db_session(db_path, connection) as conn:
        rows = conn.execute(
            """
            SELECT ticker FROM watchlist
            WHERE user_id = ?
            ORDER BY added_at, rowid
            """,
            (user_id,),
        ).fetchall()
        return [row["ticker"] for row in rows]


def add_watchlist_ticker(
    ticker: str,
    user_id: str = DEFAULT_USER_ID,
    *,
    db_path: str | Path | None = None,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    symbol = validate_ticker(ticker)
    now = utc_now_iso()
    with db_session(db_path, connection) as conn:
        cursor = conn.execute(
            """
            INSERT INTO watchlist (id, user_id, ticker, added_at)
            VALUES (lower(hex(randomblob(16))), ?, ?, ?)
            ON CONFLICT(user_id, ticker) DO NOTHING
            """,
            (user_id, symbol, now),
        )
        return {"ticker": symbol, "added": cursor.rowcount > 0}


def remove_watchlist_ticker(
    ticker: str,
    user_id: str = DEFAULT_USER_ID,
    *,
    db_path: str | Path | None = None,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    symbol = validate_ticker(ticker)
    with db_session(db_path, connection) as conn:
        cursor = conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
            (user_id, symbol),
        )
        return {"ticker": symbol, "removed": cursor.rowcount > 0}


def get_positions(
    user_id: str = DEFAULT_USER_ID,
    *,
    db_path: str | Path | None = None,
    connection: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    with db_session(db_path, connection) as conn:
        rows = conn.execute(
            """
            SELECT * FROM positions
            WHERE user_id = ?
            ORDER BY ticker
            """,
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_position(
    ticker: str,
    user_id: str = DEFAULT_USER_ID,
    *,
    db_path: str | Path | None = None,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any] | None:
    symbol = validate_ticker(ticker)
    with db_session(db_path, connection) as conn:
        row = conn.execute(
            "SELECT * FROM positions WHERE user_id = ? AND ticker = ?",
            (user_id, symbol),
        ).fetchone()
        return row_to_dict(row)


def execute_trade(
    *,
    ticker: str,
    side: str,
    quantity: Any,
    price: Any,
    user_id: str = DEFAULT_USER_ID,
    db_path: str | Path | None = None,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    symbol = validate_ticker(ticker)
    normalized_side = side.strip().lower()
    if normalized_side not in {"buy", "sell"}:
        raise TradeExecutionError(
            "INVALID_SIDE", "Trade side must be 'buy' or 'sell'.", {"side": side}
        )
    trade_quantity = validate_quantity(quantity)
    trade_price = _validate_price(price)

    with db_session(db_path, connection) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            result = _execute_trade_in_transaction(
                conn,
                user_id=user_id,
                ticker=symbol,
                side=normalized_side,
                quantity=trade_quantity,
                price=trade_price,
            )
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()
            return result.to_dict()


def _execute_trade_in_transaction(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    ticker: str,
    side: str,
    quantity: float,
    price: float,
) -> TradeResult:
    now = utc_now_iso()
    user = conn.execute("SELECT * FROM users_profile WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        raise TradeExecutionError("USER_NOT_FOUND", f"User profile '{user_id}' does not exist.")

    cash_balance = float(user["cash_balance"])
    position = conn.execute(
        "SELECT * FROM positions WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    ).fetchone()
    current_quantity = float(position["quantity"]) if position else 0.0
    current_avg_cost = float(position["avg_cost"]) if position else 0.0
    notional = round(quantity * price, 8)

    if side == "buy":
        if cash_balance + 1e-9 < notional:
            raise TradeExecutionError(
                "INSUFFICIENT_CASH",
                f"Not enough cash to buy {quantity:g} shares of {ticker}.",
                {
                    "ticker": ticker,
                    "required_cash": notional,
                    "available_cash": cash_balance,
                },
            )
        new_cash = cash_balance - notional
        new_quantity = current_quantity + quantity
        new_avg_cost = ((current_quantity * current_avg_cost) + notional) / new_quantity
        _upsert_position(conn, user_id, ticker, new_quantity, new_avg_cost, now)
    else:
        if current_quantity + 1e-9 < quantity:
            raise TradeExecutionError(
                "INSUFFICIENT_SHARES",
                f"Not enough shares to sell {quantity:g} shares of {ticker}.",
                {
                    "ticker": ticker,
                    "requested_quantity": quantity,
                    "available_quantity": current_quantity,
                },
            )
        new_cash = cash_balance + notional
        remaining_quantity = current_quantity - quantity
        if remaining_quantity <= 1e-9:
            conn.execute(
                "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
                (user_id, ticker),
            )
        else:
            _upsert_position(conn, user_id, ticker, remaining_quantity, current_avg_cost, now)

    conn.execute(
        "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
        (round(new_cash, 8), user_id),
    )
    conn.execute(
        """
        INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at)
        VALUES (lower(hex(randomblob(16))), ?, ?, ?, ?, ?, ?)
        """,
        (user_id, ticker, side, quantity, price, now),
    )
    watchlist_cursor = conn.execute(
        """
        INSERT INTO watchlist (id, user_id, ticker, added_at)
        VALUES (lower(hex(randomblob(16))), ?, ?, ?)
        ON CONFLICT(user_id, ticker) DO NOTHING
        """,
        (user_id, ticker, now),
    )
    trade_row = conn.execute(
        """
        SELECT * FROM trades
        WHERE user_id = ? AND ticker = ? AND executed_at = ?
        ORDER BY rowid DESC
        LIMIT 1
        """,
        (user_id, ticker, now),
    ).fetchone()
    updated_position = conn.execute(
        "SELECT * FROM positions WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    ).fetchone()
    portfolio_total = round(
        float(new_cash) + sum(float(row["quantity"]) * price for row in _position_rows(conn, user_id)),
        8,
    )
    _record_portfolio_snapshot_in_transaction(conn, user_id, portfolio_total, now)

    return TradeResult(
        trade=dict(trade_row),
        cash_balance=round(float(new_cash), 8),
        position=row_to_dict(updated_position),
        portfolio_total=portfolio_total,
        added_to_watchlist=watchlist_cursor.rowcount > 0,
    )


def _upsert_position(
    conn: sqlite3.Connection,
    user_id: str,
    ticker: str,
    quantity: float,
    avg_cost: float,
    now: str,
) -> None:
    conn.execute(
        """
        INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at)
        VALUES (lower(hex(randomblob(16))), ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, ticker)
        DO UPDATE SET quantity = excluded.quantity,
                      avg_cost = excluded.avg_cost,
                      updated_at = excluded.updated_at
        """,
        (user_id, ticker, round(quantity, 8), round(avg_cost, 8), now),
    )


def _position_rows(conn: sqlite3.Connection, user_id: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM positions WHERE user_id = ?", (user_id,)).fetchall()


def list_trades(
    user_id: str = DEFAULT_USER_ID,
    *,
    limit: int = 100,
    db_path: str | Path | None = None,
    connection: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    bounded_limit = _bounded_limit(limit, default=100, maximum=DEFAULT_SNAPSHOT_LIMIT)
    with db_session(db_path, connection) as conn:
        rows = conn.execute(
            """
            SELECT * FROM trades
            WHERE user_id = ?
            ORDER BY executed_at DESC, rowid DESC
            LIMIT ?
            """,
            (user_id, bounded_limit),
        ).fetchall()
        return [dict(row) for row in rows]


def record_portfolio_snapshot(
    total_value: Any,
    user_id: str = DEFAULT_USER_ID,
    *,
    limit: int = DEFAULT_SNAPSHOT_LIMIT,
    db_path: str | Path | None = None,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    value = _validate_non_negative_float(total_value, "INVALID_TOTAL_VALUE")
    with db_session(db_path, connection) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = _record_portfolio_snapshot_in_transaction(conn, user_id, value, utc_now_iso(), limit)
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()
            return row


def _record_portfolio_snapshot_in_transaction(
    conn: sqlite3.Connection,
    user_id: str,
    total_value: float,
    recorded_at: str,
    limit: int = DEFAULT_SNAPSHOT_LIMIT,
) -> dict[str, Any]:
    conn.execute(
        """
        INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at)
        VALUES (lower(hex(randomblob(16))), ?, ?, ?)
        """,
        (user_id, round(total_value, 8), recorded_at),
    )
    _prune_portfolio_snapshots(conn, user_id, limit)
    row = conn.execute(
        """
        SELECT * FROM portfolio_snapshots
        WHERE user_id = ?
        ORDER BY recorded_at DESC, rowid DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    return dict(row)


def get_portfolio_snapshots(
    user_id: str = DEFAULT_USER_ID,
    *,
    limit: int = 500,
    db_path: str | Path | None = None,
    connection: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    bounded_limit = _bounded_limit(limit, default=500, maximum=DEFAULT_SNAPSHOT_LIMIT)
    with db_session(db_path, connection) as conn:
        rows = conn.execute(
            """
            SELECT * FROM portfolio_snapshots
            WHERE user_id = ?
            ORDER BY recorded_at DESC, rowid DESC
            LIMIT ?
            """,
            (user_id, bounded_limit),
        ).fetchall()
        return [dict(row) for row in reversed(rows)]


def _prune_portfolio_snapshots(
    conn: sqlite3.Connection, user_id: str, limit: int = DEFAULT_SNAPSHOT_LIMIT
) -> None:
    bounded_limit = _bounded_limit(limit, default=DEFAULT_SNAPSHOT_LIMIT, maximum=DEFAULT_SNAPSHOT_LIMIT)
    conn.execute(
        """
        DELETE FROM portfolio_snapshots
        WHERE user_id = ?
          AND rowid NOT IN (
              SELECT rowid FROM portfolio_snapshots
              WHERE user_id = ?
              ORDER BY recorded_at DESC, rowid DESC
              LIMIT ?
          )
        """,
        (user_id, user_id, bounded_limit),
    )


def add_chat_message(
    *,
    role: str,
    content: str,
    actions: Any | None = None,
    user_id: str = DEFAULT_USER_ID,
    db_path: str | Path | None = None,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    normalized_role = role.strip().lower()
    if normalized_role not in {"user", "assistant"}:
        raise DatabaseValidationError(
            "INVALID_CHAT_ROLE", "Chat role must be 'user' or 'assistant'.", {"role": role}
        )
    if not isinstance(content, str) or not content.strip():
        raise DatabaseValidationError("INVALID_CHAT_CONTENT", "Chat content must be non-empty.")
    actions_json = (
        json.dumps(actions, separators=(",", ":"), sort_keys=True) if actions is not None else None
    )
    now = utc_now_iso()
    with db_session(db_path, connection) as conn:
        row = conn.execute(
            """
            INSERT INTO chat_messages (id, user_id, role, content, actions, created_at)
            VALUES (lower(hex(randomblob(16))), ?, ?, ?, ?, ?)
            RETURNING *
            """,
            (user_id, normalized_role, content, actions_json, now),
        ).fetchone()
        return _decode_chat_actions(dict(row))


def get_chat_messages(
    user_id: str = DEFAULT_USER_ID,
    *,
    limit: int = 50,
    db_path: str | Path | None = None,
    connection: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    bounded_limit = _bounded_limit(limit, default=50, maximum=500)
    with db_session(db_path, connection) as conn:
        rows = conn.execute(
            """
            SELECT * FROM chat_messages
            WHERE user_id = ?
            ORDER BY created_at DESC, rowid DESC
            LIMIT ?
            """,
            (user_id, bounded_limit),
        ).fetchall()
        return [_decode_chat_actions(dict(row)) for row in reversed(rows)]


def _decode_chat_actions(message: dict[str, Any]) -> dict[str, Any]:
    if message.get("actions") is not None:
        message["actions"] = json.loads(message["actions"])
    return message


def _validate_non_negative_float(value: Any, code: str) -> float:
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        raise DatabaseValidationError(code, "Value must be numeric.") from None
    if not math.isfinite(numeric_value) or numeric_value < 0:
        raise DatabaseValidationError(code, "Value must be non-negative.")
    return numeric_value


def _bounded_limit(limit: int, *, default: int, maximum: int) -> int:
    try:
        numeric_limit = int(limit)
    except (TypeError, ValueError):
        return default
    if numeric_limit <= 0:
        return default
    return min(numeric_limit, maximum)
