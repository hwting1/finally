"""SQLite schema creation and seed data."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.db.connection import connect

DEFAULT_USER_ID = "default"
DEFAULT_WATCHLIST_TICKERS = (
    "AAPL",
    "GOOGL",
    "MSFT",
    "AMZN",
    "TSLA",
    "NVDA",
    "META",
    "JPM",
    "V",
    "NFLX",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users_profile (
    id TEXT PRIMARY KEY DEFAULT 'default',
    cash_balance REAL NOT NULL DEFAULT 10000.0 CHECK (cash_balance >= 0),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    added_at TEXT NOT NULL,
    UNIQUE (user_id, ticker),
    FOREIGN KEY (user_id) REFERENCES users_profile(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS positions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    quantity REAL NOT NULL CHECK (quantity > 0),
    avg_cost REAL NOT NULL CHECK (avg_cost > 0),
    updated_at TEXT NOT NULL,
    UNIQUE (user_id, ticker),
    FOREIGN KEY (user_id) REFERENCES users_profile(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS trades (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity REAL NOT NULL CHECK (quantity > 0),
    price REAL NOT NULL CHECK (price > 0),
    executed_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users_profile(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    total_value REAL NOT NULL CHECK (total_value >= 0),
    recorded_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users_profile(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    actions TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users_profile(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_watchlist_user_added
    ON watchlist(user_id, added_at);
CREATE INDEX IF NOT EXISTS idx_positions_user_ticker
    ON positions(user_id, ticker);
CREATE INDEX IF NOT EXISTS idx_trades_user_executed
    ON trades(user_id, executed_at DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_user_recorded
    ON portfolio_snapshots(user_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_user_created
    ON chat_messages(user_id, created_at DESC);
"""


def initialize_database(path: str | Path | None = None) -> None:
    with connect(path) as connection:
        initialize_connection(connection)


def initialize_connection(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA_SQL)
    seed_defaults(connection)
    connection.commit()


def seed_defaults(connection: sqlite3.Connection) -> None:
    now = utc_now_iso()
    connection.execute(
        """
        INSERT INTO users_profile (id, cash_balance, created_at)
        VALUES (?, ?, ?)
        ON CONFLICT(id) DO NOTHING
        """,
        (DEFAULT_USER_ID, 10000.0, now),
    )
    for ticker in DEFAULT_WATCHLIST_TICKERS:
        connection.execute(
            """
            INSERT INTO watchlist (id, user_id, ticker, added_at)
            VALUES (lower(hex(randomblob(16))), ?, ?, ?)
            ON CONFLICT(user_id, ticker) DO NOTHING
            """,
            (DEFAULT_USER_ID, ticker, now),
        )
