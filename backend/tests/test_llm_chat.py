from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.llm.client import MockStructuredChatClient, validate_structured_plan
from app.llm.models import (
    ChatMessageRecord,
    ChatRole,
    LLMChatPlan,
    LLMTradeAction,
    PortfolioContext,
    PositionContext,
    TradeSide,
    WatchlistQuoteContext,
)
from app.llm.service import FinAllyChatService
from app.main import create_app


class FakeHistoryStore:
    def __init__(self) -> None:
        self.saved: list[ChatMessageRecord] = []

    async def recent_messages(self, user_id: str, limit: int = 20) -> list[ChatMessageRecord]:
        return self.saved[-limit:]

    async def save_message(
        self,
        user_id: str,
        role: str,
        content: str,
        actions: list[dict[str, Any]] | None = None,
    ) -> ChatMessageRecord:
        record = ChatMessageRecord(
            id=str(len(self.saved) + 1),
            user_id=user_id,
            role=ChatRole(role),
            content=content,
            actions=actions,
        )
        self.saved.append(record)
        return record


class FakePortfolioReader:
    def __init__(self) -> None:
        self.context = PortfolioContext(
            user_id="default",
            cash_balance=10_000,
            total_value=10_000,
            positions=[PositionContext(ticker="MSFT", quantity=2, current_price=300)],
            watchlist=[WatchlistQuoteContext(ticker="AAPL", price=190)],
        )

    async def get_portfolio_context(self, user_id: str) -> PortfolioContext:
        return self.context


class FakeTradeExecutor:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute_trade(
        self,
        user_id: str,
        ticker: str,
        side: TradeSide,
        quantity: float,
        source: str = "ai",
    ) -> dict[str, Any]:
        payload = {
            "user_id": user_id,
            "ticker": ticker,
            "side": side.value,
            "quantity": quantity,
            "source": source,
        }
        self.calls.append(payload)
        return {"trade": payload, "portfolio_total": 10_000}


class FakeWatchlistExecutor:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def change_watchlist(
        self,
        user_id: str,
        ticker: str,
        action: str,
        source: str = "ai",
    ) -> dict[str, Any]:
        payload = {
            "user_id": user_id,
            "ticker": ticker,
            "action": action.value,
            "source": source,
        }
        self.calls.append(payload)
        return {"watchlist": payload}


class StaticClient:
    def __init__(self, plan: LLMChatPlan) -> None:
        self.plan = plan

    async def complete(self, messages: list[dict[str, str]]) -> LLMChatPlan:
        return self.plan


def make_service(client: Any) -> tuple[FinAllyChatService, FakeHistoryStore, FakeTradeExecutor]:
    history = FakeHistoryStore()
    trades = FakeTradeExecutor()
    service = FinAllyChatService(
        settings=Settings(llm_mock=True),
        client=client,
        history_store=history,
        portfolio_reader=FakePortfolioReader(),
        trade_executor=trades,
        watchlist_executor=FakeWatchlistExecutor(),
    )
    return service, history, trades


def test_chat_endpoint_returns_disabled_error_without_key_or_mock(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            database_path=str(tmp_path / "finally-test.db"),
            llm_api_key="",
            llm_mock=False,
            market_poll_interval_seconds=0.5,
        )
    )

    with TestClient(app) as client:
        response = client.post("/api/chat", json={"message": "analyze my portfolio"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "LLM_CHAT_DISABLED"


@pytest.mark.anyio
async def test_mock_chat_executes_trade_and_persists_history() -> None:
    service, history, trades = make_service(MockStructuredChatClient())

    response = await service.chat(user_id="default", message="buy 2 AAPL")

    assert response.message == "Mock response prepared the requested portfolio actions."
    assert response.actions[0].status == "executed"
    assert trades.calls == [
        {
            "user_id": "default",
            "ticker": "AAPL",
            "side": "buy",
            "quantity": 2.0,
            "source": "ai",
        }
    ]
    assert [message.role for message in history.saved] == [ChatRole.USER, ChatRole.ASSISTANT]
    assert history.saved[-1].actions[0]["status"] == "executed"


@pytest.mark.anyio
async def test_ai_action_limit_rejects_excess_actions_independently() -> None:
    plan = LLMChatPlan(
        message="placing trades",
        trades=[
            LLMTradeAction(ticker="AAPL", side="buy", quantity=1),
            LLMTradeAction(ticker="AAPL", side="buy", quantity=1),
            LLMTradeAction(ticker="AAPL", side="buy", quantity=1),
            LLMTradeAction(ticker="AAPL", side="buy", quantity=1),
            LLMTradeAction(ticker="AAPL", side="buy", quantity=1),
            LLMTradeAction(ticker="AAPL", side="buy", quantity=1),
        ],
    )
    service, _, trades = make_service(StaticClient(plan))

    response = await service.chat(user_id="default", message="buy many")

    assert [action.status for action in response.actions] == [
        "executed",
        "executed",
        "executed",
        "executed",
        "executed",
        "rejected",
    ]
    assert response.actions[-1].code == "AI_ACTION_LIMIT_EXCEEDED"
    assert len(trades.calls) == 5


@pytest.mark.anyio
async def test_ai_notional_guardrail_rejects_large_trade() -> None:
    plan = LLMChatPlan(
        message="large trade",
        trades=[LLMTradeAction(ticker="AAPL", side="buy", quantity=30)],
    )
    service, _, trades = make_service(StaticClient(plan))

    response = await service.chat(user_id="default", message="buy 30 AAPL")

    assert response.actions[0].status == "rejected"
    assert response.actions[0].code == "AI_ORDER_NOTIONAL_LIMIT_EXCEEDED"
    assert trades.calls == []


def test_structured_output_validation_rejects_malformed_payload() -> None:
    with pytest.raises(Exception, match="required schema"):
        validate_structured_plan({"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 1}]})


@pytest.mark.anyio
async def test_mock_chat_parses_plain_english_share_phrase() -> None:
    plan = await MockStructuredChatClient().complete(
        [{"role": "user", "content": "Use mock mode to buy one share of AAPL."}]
    )

    assert plan.trades[0].ticker == "AAPL"
    assert plan.trades[0].quantity == 1


@pytest.mark.anyio
async def test_mock_chat_does_not_turn_buy_now_question_into_trade() -> None:
    plan = await MockStructuredChatClient().complete(
        [{"role": "user", "content": "What should I buy now"}]
    )

    assert plan.message == "Mock analysis complete."
    assert plan.trades == []
