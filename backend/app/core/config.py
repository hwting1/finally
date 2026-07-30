"""Centralized runtime settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    massive_api_key: str = ""
    market_poll_interval_seconds: float | None = None
    market_stale_after_seconds: float = 30.0
    market_simulator_seed: int = 42


settings = Settings()
