"""Centralized runtime settings."""

from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    llm_api_key: str = ""
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    llm_model: str = "gemini-3-flash-preview"
    llm_mock: bool = False
    llm_max_actions: int = 5
    llm_max_order_notional_portfolio_fraction: float = 0.5

    database_path: str = "../db/finally.db"
    massive_api_key: str = ""
    market_poll_interval_seconds: float | None = None
    market_stale_after_seconds: float = 30.0
    market_simulator_seed: int = 42

    @field_validator("market_poll_interval_seconds", mode="before")
    @classmethod
    def blank_market_poll_interval_is_unset(cls, value: object) -> object:
        if value == "":
            return None
        return value


settings = Settings()
