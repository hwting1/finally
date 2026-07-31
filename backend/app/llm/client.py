"""OpenAI SDK and deterministic mock clients for structured chat responses."""

from __future__ import annotations

import re
from typing import Any, Protocol

from pydantic import ValidationError

from app.core.config import Settings
from app.llm.models import LLMChatPlan, LLMTradeAction, LLMWatchlistChange
from app.market.validation import normalize_ticker


class LLMConfigurationError(RuntimeError):
    """Raised when chat is intentionally disabled by missing configuration."""


class LLMProviderError(RuntimeError):
    """Raised when the configured provider returns malformed or failed output."""


class StructuredChatClient(Protocol):
    async def complete(self, messages: list[dict[str, str]]) -> LLMChatPlan:
        """Return a validated structured chat plan."""


class OpenAIStructuredChatClient:
    def __init__(self, client: Any, model: str) -> None:
        self._client = client
        self._model = model

    async def complete(self, messages: list[dict[str, str]]) -> LLMChatPlan:
        try:
            response = self._client.beta.chat.completions.parse(
                model=self._model,
                messages=messages,
                response_format=LLMChatPlan,
            )
        except Exception as exc:  # SDK/provider exceptions are normalized at the API edge.
            raise LLMProviderError("LLM provider failed to return structured output.") from exc

        parsed = response.choices[0].message.parsed
        if not isinstance(parsed, LLMChatPlan):
            raise LLMProviderError("LLM provider response did not match the chat schema.")
        return parsed


class MockStructuredChatClient:
    """Deterministic parser for development, unit tests, and E2E tests."""

    _ignored_trade_words = {"NOW", "TODAY"}
    _number_words = {
        "one": 1.0,
        "two": 2.0,
        "three": 3.0,
        "four": 4.0,
        "five": 5.0,
        "ten": 10.0,
    }
    _trade_pattern = re.compile(
        r"\b(?P<side>buy|sell)\s+"
        r"(?P<quantity>\d+(?:\.\d{1,6})?|one|two|three|four|five|ten)\s+"
        r"(?:(?:shares?|share)\s+(?:of\s+)?)?"
        r"(?P<ticker>[A-Za-z]{1,5})\b",
        re.IGNORECASE,
    )
    _watchlist_pattern = re.compile(
        r"\b(?P<action>add|remove)\s+(?P<ticker>[A-Za-z]{1,5})\b", re.IGNORECASE
    )

    async def complete(self, messages: list[dict[str, str]]) -> LLMChatPlan:
        user_message = _last_user_message(messages)
        trades = [
            LLMTradeAction(
                ticker=ticker,
                side=match.group("side").lower(),
                quantity=self._quantity(match.group("quantity")),
            )
            for match in self._trade_pattern.finditer(user_message)
            if (ticker := normalize_ticker(match.group("ticker"))) not in self._ignored_trade_words
        ]
        watchlist_changes = [
            LLMWatchlistChange(
                ticker=normalize_ticker(match.group("ticker")),
                action=match.group("action").lower(),
            )
            for match in self._watchlist_pattern.finditer(user_message)
            if match.group("action").lower() in {"add", "remove"}
        ]
        message = "Mock analysis complete."
        if trades or watchlist_changes:
            message = "Mock response prepared the requested portfolio actions."
        return LLMChatPlan(message=message, trades=trades, watchlist_changes=watchlist_changes)

    def _quantity(self, value: str | None) -> float:
        if value is None:
            return 1.0
        lowered = value.lower()
        if lowered in self._number_words:
            return self._number_words[lowered]
        return float(value)


def create_structured_chat_client(settings: Settings) -> StructuredChatClient:
    if settings.llm_mock:
        return MockStructuredChatClient()
    if not settings.llm_api_key.strip():
        raise LLMConfigurationError("LLM_API_KEY is required when LLM_MOCK is false.")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise LLMConfigurationError("The openai package is required for live LLM chat.") from exc
    client = OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url.strip() or None,
    )
    return OpenAIStructuredChatClient(client=client, model=settings.llm_model)


def validate_structured_plan(payload: object) -> LLMChatPlan:
    try:
        return LLMChatPlan.model_validate(payload)
    except ValidationError as exc:
        raise LLMProviderError("LLM response did not match the required schema.") from exc


def _last_user_message(messages: list[dict[str, str]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return message.get("content", "")
    return ""
