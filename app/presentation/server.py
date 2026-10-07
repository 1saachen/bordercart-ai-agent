# -*- coding: utf-8 -*-
"""FastAPI 服务入口

路由：
    POST /commerce/intents                 提交买家意图（当前进程同步执行）
    WS   /commerce/events                  订阅会话事件流
    GET  /commerce/orders/{order_id}       查询订单（直连 UseCase，不过 Agent）
    POST /commerce/orders/{order_id}/cancel  取消订单（直连 UseCase）
    GET  /health                           健康检查（SQLite、交易库、Qdrant 与源码指纹）

启动：
    uv run uvicorn app.presentation.server:app --port 8000
单进程运行，不需要额外 worker。
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text

from app.application.agents.orchestrator import SubmitIntentInput
from app.composition import Container, build_container
from app.presentation.connection import ConnectionManager
from app.presentation.confirmations import register_confirmation_routes, confirmation_error
from app.presentation.ag_ui import register_ag_ui_routes
from app.presentation.buyer_workspace import register_buyer_workspace_routes
from app.presentation.identity import require_buyer, require_session
from app.presentation.dto import (
    CancelOrderRequest,
    SubmitIntentRequest,
    SubmitIntentResponse,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

logger = logging.getLogger(__name__)

def build_app() -> FastAPI:
    state: dict = {}

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        c = await build_container()
        state["c"] = c
        application.state.identity_policy = getattr(c, "identity_policy", None)
        application.state.session_store = getattr(c, "session_store", None)
        application.state.session_owner_binding = getattr(getattr(c, "settings", None), "session_owner_binding", True)
        state["connections"] = ConnectionManager(c.bus)
        await c.startup()
        try:
            yield
        finally:
            state.pop("c", None)
            await c.shutdown()

    api = FastAPI(title="BorderCart AI 跨境智选助手", version="0.4.0", lifespan=lifespan)

    def container() -> Container:
        if "c" not in state:
            raise HTTPException(status_code=503, detail="服务尚未就绪")
        return state["c"]

    settings_origins = build_container_origins()
    api.add_middleware(
        CORSMiddleware,
        allow_origins=settings_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Trace-ID"],
    )

    # AG-UI 与同步意图接口都在当前进程内执行。
    register_ag_ui_routes(api, lambda: container().orchestrator, lambda: container().confirmations,
                         lambda: container().ag_ui_runtime)
    from app.presentation.context_workspace import register_context_routes
    register_context_routes(api, lambda: container().context_service)
    register_confirmation_routes(api, lambda: container().confirmations)
    register_buyer_workspace_routes(api, lambda: container().orchestrator)
    from app.presentation.shopping_forms import register_shopping_form_routes
    register_shopping_form_routes(api, lambda: container().orchestrator._sessions._main_factory.shopping_form_store)
    from app.presentation.favorites import register_favorite_routes
    from app.infrastructure.buyer_favorites import BuyerFavoriteStore
    register_favorite_routes(api, lambda: BuyerFavoriteStore(container().settings.data_dir / "buyer_favorites.db"))

    @api.get("/health")
    async def health() -> dict:
        """依赖连通性一并报出，避免"进程活着但存储已挂"被当成健康。"""
        c = container()
        database = "disabled"
        if c.db_engine is not None:
            try:
                async with c.db_engine.connect() as conn:
                    await conn.execute(text("select 1"))
                database = c.db_engine.url.get_backend_name()
            except Exception as err:  # noqa: BLE001
                database = f"error: {err}"
        trade_database = "disabled"
        trade_engine = getattr(c, "trade_db_engine", None)
        if trade_engine is not None:
            try:
                async with trade_engine.connect() as conn:
                    await conn.execute(text("select 1"))
                trade_database = trade_engine.url.get_backend_name()
            except Exception:
                trade_database = "error"
        try:
            qdrant = await c.vector_index.health()
        except Exception:
            qdrant = "error"
        ready = not database.startswith("error") and trade_database != "error" and qdrant != "error"
        result = {
            "status": "ok" if ready else "degraded",
            "model": c.settings.llm_model,
            "runtime": getattr(c, "runtime", {}),
            "database": database,
            "trade_database": trade_database,
            "qdrant": qdrant,
        }
        return result if ready else JSONResponse(status_code=503, content=result)

    @api.post("/commerce/intents", response_model=SubmitIntentResponse)
    async def submit_intent(request: Request, body: SubmitIntentRequest) -> SubmitIntentResponse:
        c = container()
        session_id = body.shopping_session_id or f"session-{uuid.uuid4().hex[:8]}"
        body.buyer_id = await require_buyer(request, body.buyer_id)
        await require_session(request, body.buyer_id, session_id, create=True)
        intent = SubmitIntentInput(
            shopping_session_id=session_id,
            buyer_id=body.buyer_id,
            locale=body.locale,
            currency=body.currency,
            raw_query=body.raw_query,
        )
        result = await c.orchestrator.handle_intent(intent)
        return SubmitIntentResponse(shopping_session_id=result.shopping_session_id, final_text=result.final_text)

    @api.websocket("/commerce/events")
    async def commerce_events(websocket: WebSocket) -> None:
        await state["connections"].serve(websocket)

    @api.get("/commerce/orders")
    async def list_orders(request: Request, buyer_id: str = Query(min_length=1),
                          status: str | None = Query(default=None, pattern="^(CONFIRMED|CANCELLED|DRAFT)$"),
                          offset: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=100)) -> dict:
        buyer = await require_buyer(request, buyer_id)
        return await container().trade_store.list_orders(buyer_id=buyer, status=status, offset=offset, limit=limit)

    @api.get("/commerce/orders/{order_id}")
    async def get_order(request: Request, order_id: str, buyer_id: str = Query(min_length=1)) -> dict:
        buyer_id = await require_buyer(request, buyer_id)
        try:
            return await container().query_order.execute(order_id, buyer_id=buyer_id)
        except ValueError as err:
            raise HTTPException(status_code=404, detail=str(err)) from err

    @api.post("/commerce/orders/{order_id}/cancel")
    async def cancel_order_endpoint(request: Request, order_id: str, body: CancelOrderRequest) -> dict:
        body.buyer_id = await require_buyer(request, body.buyer_id)
        await require_session(request, body.buyer_id, body.session_id, create=True)
        try:
            return await container().cancel_order.execute(order_id, body.reason, buyer_id=body.buyer_id, session_id=body.session_id)
        except ValueError as err:
            raise confirmation_error(err) from err

    return api


def build_container_origins() -> list[str]:
    """CORS 需要在 app 构造期就确定，此处单独读一次配置。"""
    from app.infrastructure.settings import load_settings

    return load_settings().cors_origins


app = build_app()


if __name__ == "__main__":
    import uvicorn

    from app.infrastructure.settings import load_settings

    uvicorn.run(app, host="0.0.0.0", port=load_settings().port)
