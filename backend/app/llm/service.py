"""FinAlly chat orchestration, guardrails, and action execution."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings
from app.llm.client import LLMConfigurationError, LLMProviderError, StructuredChatClient
from app.llm.interfaces import (
    ChatHistoryStore,
    PortfolioContextReader,
    TradeExecutor,
    WatchlistExecutor,
)
from app.llm.models import (
    ActionResult,
    ChatResponse,
    LLMChatPlan,
    LLMTradeAction,
    LLMWatchlistChange,
    PortfolioContext,
    is_valid_trade_action,
    quantity_has_valid_precision,
)
from app.market.validation import is_valid_ticker


SYSTEM_PROMPT = """You are FinAlly, an AI trading assistant for a simulated portfolio.
Analyze portfolio composition, risk concentration, prices, and P&L.
Be concise and data-driven.
When the user explicitly asks you to trade or manage the watchlist, include those actions.
Always return valid structured output matching the requested schema."""


class MissingLLMDependencyError(RuntimeError):
    """Raised when the route is enabled before DB/API service dependencies are wired."""


class FinAllyChatService:
    def __init__(
        self,
        settings: Settings,
        client: StructuredChatClient,
        history_store: ChatHistoryStore,
        portfolio_reader: PortfolioContextReader,
        trade_executor: TradeExecutor,
        watchlist_executor: WatchlistExecutor,
    ) -> None:
        self._settings = settings
        self._client = client
        self._history_store = history_store
        self._portfolio_reader = portfolio_reader
        self._trade_executor = trade_executor
        self._watchlist_executor = watchlist_executor

    async def chat(self, user_id: str, message: str) -> ChatResponse:
        portfolio = await self._portfolio_reader.get_portfolio_context(user_id)
        history = await self._history_store.recent_messages(user_id=user_id, limit=20)
        messages = _build_messages(portfolio=portfolio, history=history, user_message=message)

        await self._history_store.save_message(user_id=user_id, role="user", content=message)
        plan = await self._client.complete(messages)
        actions = await self._execute_actions(user_id=user_id, portfolio=portfolio, plan=plan)
        action_payload = [action.model_dump(mode="json") for action in actions]
        await self._history_store.save_message(
            user_id=user_id,
            role="assistant",
            content=plan.message,
            actions=action_payload,
        )
        return ChatResponse(message=plan.message, actions=actions)

    async def _execute_actions(
        self, user_id: str, portfolio: PortfolioContext, plan: LLMChatPlan
    ) -> list[ActionResult]:
        requested_actions: list[LLMTradeAction | LLMWatchlistChange] = [
            *plan.trades,
            *plan.watchlist_changes,
        ]
        results: list[ActionResult] = []
        for index, action in enumerate(requested_actions):
            if index >= self._settings.llm_max_actions:
                results.append(
                    _rejected_result(
                        action,
                        code="AI_ACTION_LIMIT_EXCEEDED",
                        message=f"Only {self._settings.llm_max_actions} AI actions are allowed per response.",
                    )
                )
                continue
            if isinstance(action, LLMTradeAction):
                results.append(await self._execute_trade_action(user_id, portfolio, action))
            else:
                results.append(await self._execute_watchlist_action(user_id, action))
        return results

    async def _execute_trade_action(
        self, user_id: str, portfolio: PortfolioContext, action: LLMTradeAction
    ) -> ActionResult:
        validation_error = _validate_trade_action(
            action,
            portfolio=portfolio,
            max_notional_fraction=self._settings.llm_max_order_notional_portfolio_fraction,
        )
        if validation_error is not None:
            return validation_error
        try:
            result = await self._trade_executor.execute_trade(
                user_id=user_id,
                ticker=action.ticker,
                side=action.side,
                quantity=action.quantity,
                source="ai",
            )
        except Exception as exc:
            return _failed_result(action, code="TRADE_EXECUTION_FAILED", message=str(exc))
        return ActionResult(
            type="trade",
            requested=action.model_dump(mode="json"),
            status="executed",
            code="EXECUTED",
            message=f"Executed {action.side.value} order for {action.quantity:g} {action.ticker}.",
            timestamp=_now(),
            result=result,
        )

    async def _execute_watchlist_action(
        self, user_id: str, action: LLMWatchlistChange
    ) -> ActionResult:
        if not is_valid_ticker(action.ticker):
            return _rejected_result(
                action,
                code="INVALID_TICKER",
                message=f"{action.ticker} is not a supported ticker symbol.",
            )
        try:
            result = await self._watchlist_executor.change_watchlist(
                user_id=user_id,
                ticker=action.ticker,
                action=action.action,
                source="ai",
            )
        except Exception as exc:
            return _failed_result(action, code="WATCHLIST_UPDATE_FAILED", message=str(exc))
        return ActionResult(
            type="watchlist",
            requested=action.model_dump(mode="json"),
            status="executed",
            code="EXECUTED",
            message=f"Watchlist {action.action.value} applied for {action.ticker}.",
            timestamp=_now(),
            result=result,
        )


def _build_messages(portfolio: PortfolioContext, history: list[Any], user_message: str) -> list[dict[str, str]]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Current portfolio context JSON: {portfolio.model_dump_json()}"},
    ]
    messages.extend(
        {"role": item.role.value if hasattr(item.role, "value") else str(item.role), "content": item.content}
        for item in history
    )
    messages.append({"role": "user", "content": user_message})
    return messages


def _validate_trade_action(
    action: LLMTradeAction,
    portfolio: PortfolioContext,
    max_notional_fraction: float,
) -> ActionResult | None:
    if not is_valid_trade_action(action):
        if not is_valid_ticker(action.ticker):
            code = "INVALID_TICKER"
            message = f"{action.ticker} is not a supported ticker symbol."
        elif action.quantity <= 0:
            code = "INVALID_QUANTITY"
            message = "Trade quantity must be greater than zero."
        elif not quantity_has_valid_precision(action.quantity):
            code = "INVALID_QUANTITY_PRECISION"
            message = "Trade quantity supports at most 6 decimal places."
        else:
            code = "INVALID_TRADE"
            message = "Trade action failed validation."
        return _rejected_result(action, code=code, message=message)

    price = portfolio.price_for(action.ticker)
    if price is None or price <= 0:
        return _rejected_result(
            action,
            code="MARKET_PRICE_UNAVAILABLE",
            message=f"No current market price is available for {action.ticker}.",
        )

    portfolio_value = max(portfolio.total_value, 0)
    max_notional = portfolio_value * max_notional_fraction
    requested_notional = price * action.quantity
    if portfolio_value > 0 and requested_notional > max_notional:
        return _rejected_result(
            action,
            code="AI_ORDER_NOTIONAL_LIMIT_EXCEEDED",
            message="AI-generated order exceeds 50% of current portfolio value.",
        )
    return None


def _rejected_result(
    action: LLMTradeAction | LLMWatchlistChange, code: str, message: str
) -> ActionResult:
    return ActionResult(
        type="trade" if isinstance(action, LLMTradeAction) else "watchlist",
        requested=action.model_dump(mode="json"),
        status="rejected",
        code=code,
        message=message,
        timestamp=_now(),
    )


def _failed_result(
    action: LLMTradeAction | LLMWatchlistChange, code: str, message: str
) -> ActionResult:
    return ActionResult(
        type="trade" if isinstance(action, LLMTradeAction) else "watchlist",
        requested=action.model_dump(mode="json"),
        status="failed",
        code=code,
        message=message,
        timestamp=_now(),
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def disabled_chat_error(exc: LLMConfigurationError) -> dict[str, Any]:
    return {
        "error": {
            "code": "LLM_CHAT_DISABLED",
            "message": str(exc),
            "details": {"required": "Set LLM_API_KEY or enable LLM_MOCK=true."},
        }
    }

def provider_chat_error(exc: LLMProviderError) -> dict[str, Any]:
    return {
        "error": {
            "code": "LLM_STRUCTURED_OUTPUT_ERROR",
            "message": str(exc),
            "details": {},
        }
    }
