"""SQLite connection helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.core.config import Settings, settings


def database_path(app_settings: Settings = settings) -> Path:
    return Path(app_settings.database_path).expanduser()


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    db_path = Path(path) if path is not None else database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection
