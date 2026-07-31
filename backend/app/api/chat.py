"""LLM chat API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.core.config import Settings
from app.llm.client import LLMConfigurationError, LLMProviderError, create_structured_chat_client
from app.llm.models import ChatRequest
from app.llm.service import (
    FinAllyChatService,
    MissingLLMDependencyError,
    disabled_chat_error,
    provider_chat_error,
)


router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("")
async def post_chat(payload: ChatRequest, request: Request) -> dict:
    try:
        service = get_chat_service(request)
        response = await service.chat(user_id=payload.user_id, message=payload.message)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=disabled_chat_error(exc)["error"]) from exc
    except MissingLLMDependencyError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "LLM_DEPENDENCIES_UNAVAILABLE",
                "message": str(exc),
                "details": {},
            },
        ) from exc
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=provider_chat_error(exc)["error"]) from exc
    return response.model_dump(mode="json")


def get_chat_service(request: Request) -> FinAllyChatService:
    existing = getattr(request.app.state, "chat_service", None)
    if existing is not None:
        return existing

    settings: Settings = request.app.state.settings
    client = create_structured_chat_client(settings)
    try:
        history_store = request.app.state.chat_history_store
        portfolio_reader = request.app.state.portfolio_context_reader
        trade_executor = request.app.state.trade_executor
        watchlist_executor = request.app.state.watchlist_executor
    except AttributeError as exc:
        raise MissingLLMDependencyError(
            "Chat persistence, portfolio context, trade execution, and watchlist services must be "
            "attached to app.state before live or mock chat can run."
        ) from exc

    service = FinAllyChatService(
        settings=settings,
        client=client,
        history_store=history_store,
        portfolio_reader=portfolio_reader,
        trade_executor=trade_executor,
        watchlist_executor=watchlist_executor,
    )
    request.app.state.chat_service = service
    return service
