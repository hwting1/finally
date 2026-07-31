"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from app.api import chat, market, portfolio, stream, watchlist
from app.core.config import Settings, settings
from app.core.errors import register_error_handlers
from app.market.cache import PriceCache
from app.market.provider import create_market_provider, default_poll_interval_seconds
from app.market.service import MarketDataService
from app.services.portfolio import PortfolioService, SQLiteFinAllyRepository, WatchlistService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = PROJECT_ROOT / "static"


def create_app(app_settings: Settings = settings) -> FastAPI:
    repository = SQLiteFinAllyRepository(app_settings.database_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        provider = create_market_provider(app_settings)
        cache = PriceCache(stale_after_seconds=app_settings.market_stale_after_seconds)

        async def ticker_loader() -> set[str]:
            return await repository.tracked_tickers()

        service = MarketDataService(
            provider=provider,
            cache=cache,
            ticker_loader=ticker_loader,
            poll_interval_seconds=default_poll_interval_seconds(app_settings),
        )
        portfolio_service = PortfolioService(repository, service)
        watchlist_service = WatchlistService(repository, portfolio_service)
        app.state.settings = app_settings
        app.state.repository = repository
        app.state.market_cache = cache
        app.state.market_service = service
        app.state.portfolio_service = portfolio_service
        app.state.watchlist_service = watchlist_service
        app.state.chat_history_store = repository
        app.state.portfolio_context_reader = portfolio_service
        app.state.trade_executor = portfolio_service
        app.state.watchlist_executor = watchlist_service
        await service.start()
        try:
            yield
        finally:
            await service.stop()

    fastapi_app = FastAPI(title="FinAlly Backend", lifespan=lifespan)
    register_error_handlers(fastapi_app)
    fastapi_app.include_router(market.router)
    fastapi_app.include_router(stream.router)
    fastapi_app.include_router(watchlist.router)
    fastapi_app.include_router(portfolio.router)
    fastapi_app.include_router(chat.router)

    @fastapi_app.get("/api/health")
    async def health(request: Request) -> dict:
        market_service = request.app.state.market_service
        return {
            "ok": True,
            "market": market_service.health().source.value,
            "chat_enabled": app_settings.llm_mock or bool(app_settings.llm_api_key.strip()),
        }

    if STATIC_DIR.exists():
        assets_dir = STATIC_DIR / "_next"
        if assets_dir.exists():
            fastapi_app.mount("/_next", StaticFiles(directory=assets_dir), name="next-assets")

        @fastapi_app.get("/{path:path}", include_in_schema=False)
        async def serve_frontend(path: str) -> FileResponse:
            requested = STATIC_DIR / path
            if path and requested.is_file():
                return FileResponse(requested)
            html = requested / "index.html" if path else STATIC_DIR / "index.html"
            if html.is_file():
                return FileResponse(html)
            return FileResponse(STATIC_DIR / "index.html")

    return fastapi_app


app = create_app()
