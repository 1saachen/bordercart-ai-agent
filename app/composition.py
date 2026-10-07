# -*- coding: utf-8 -*-
"""装配容器（Composition Root）

API 进程使用单一组合根，保证本地运行时所有 Agent 共享同一份依赖。
洋葱由内向外装配：infrastructure → application → （presentation 在 server.py）。

核心版固定本地单进程：SQLite、本地事件总线、Qdrant 和 AgentScope KnowledgeBase。
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from app.application.agents.main_agent import MainAgentFactory, SessionRegistry
from app.application.agents.orchestrator import MainAgentOrchestrator
from app.application.agents.search_agent import SearchAgentFactory
from app.application.agents.trade_agent import TradeAgentFactory
from app.application.memory.preference_selector import PreferenceSelector
from app.infrastructure.buyer_skills import BuyerSkillStore
from app.application.usecases.catalog_search import CatalogSearchUseCase
from app.application.usecases.confirmation_service import ConfirmationService
from app.infrastructure.persistence.sql.trade_store import SqlTradeStore
from app.application.usecases.order_usecases import (
    CancelOrderUseCase,
    PlaceOrderUseCase,
    QueryOrderUseCase,
)
from app.infrastructure.embedding.openai_embedding_client import OpenAIEmbeddingClient
from app.infrastructure.eventbus import TradeEventBus
from app.infrastructure.persistence.in_memory_repositories import (
    InMemoryProductRepository,
)
from app.infrastructure.persistence.json_file_stores import (
    JsonFileConversationStore,
    JsonFilePreferenceStore,
    JsonFileSessionStore,
)
from app.infrastructure.persistence.sql.repositories import (
    SqlConversationStore,
    SqlPreferenceStore,
    SqlSessionStore,
    bootstrap_schema,
    create_engine,
)
from app.infrastructure.rag.category_knowledge import (
    bootstrap_category_knowledge,
    build_category_knowledge_base,
)
from app.infrastructure.resilience import CircuitBreakerRegistry
from app.infrastructure.settings import Settings, load_settings
from app.infrastructure.identity import IdentityPolicy
from app.infrastructure.throttle import GatewayThrottle
from app.infrastructure.ag_ui_journal import AGUIJournal
from app.presentation.ag_ui_runtime import AGUIRuntime
from app.infrastructure.runtime_version import app_source_fingerprint
from app.infrastructure.vector.index_bootstrap import bootstrap_product_index
from app.infrastructure.vector.qdrant_product_index import QdrantProductIndex

logger = logging.getLogger(__name__)


@dataclass
class Container:
    settings: Settings
    bus: TradeEventBus
    orchestrator: MainAgentOrchestrator
    query_order: QueryOrderUseCase
    cancel_order: CancelOrderUseCase
    product_repo: InMemoryProductRepository
    embedder: Any
    vector_index: QdrantProductIndex
    knowledge_base: Any
    db_engine: Any
    confirmations: Any = None
    trade_store: Any = None
    trade_db_engine: Any = None
    runtime: dict = field(default_factory=dict)
    ag_ui_runtime: Any = None
    session_store: Any = None
    identity_policy: Any = None
    context_service: Any = None

    async def startup(self) -> None:
        """建表 / 建向量库 / 建知识库。任一失败只告警，对应能力降级但服务可用。"""
        if self.context_service is not None:
            await self.context_service.startup()
        if self.ag_ui_runtime is not None:
            await self.ag_ui_runtime.startup()
        if self.db_engine is not None and (self.trade_store is None or self.db_engine is not self.trade_db_engine):
            try:
                await bootstrap_schema(self.db_engine)
            except Exception as err:  # noqa: BLE001
                logger.warning("数据库建表失败，持久化能力不可用：%s", err)
        # 交易账本不可降级到内存：持久化失败时拒绝启动，避免返回虚假成功。
        if self.trade_store is not None:
            await self.trade_store.initialize_inventory(await self.product_repo.list_all())
            self.product_repo.bind_inventory(self.trade_store.get_inventory)
        await bootstrap_product_index(self.product_repo, self.embedder, self.vector_index)
        await bootstrap_category_knowledge(self.knowledge_base)

    async def shutdown(self) -> None:
        if self.context_service is not None:
            await self.context_service.shutdown()
        if self.ag_ui_runtime is not None:
            await self.ag_ui_runtime.shutdown()
        if isinstance(self.session_store, JsonFileSessionStore):
            await self.session_store.close()
        await self.vector_index.close()
        if self.trade_db_engine is not None and self.trade_db_engine is not self.db_engine:
            await self.trade_db_engine.dispose()
        if self.db_engine is not None:
            await self.db_engine.dispose()


async def build_container() -> Container:
    source_fingerprint = app_source_fingerprint()
    settings = load_settings()
    identity_policy = IdentityPolicy.from_settings(settings)

    # ---- Infrastructure ----
    product_repo = InMemoryProductRepository()
    bus = TradeEventBus()
    vector_index = QdrantProductIndex(settings)

    embedder = OpenAIEmbeddingClient(settings)
    knowledge_base = build_category_knowledge_base(settings)

    logger.info("核心版运行时：单进程、本地事件总线、无队列与外部缓存")

    # 存储形态
    use_database = settings.database_url != "file"
    db_engine = create_engine(settings.database_url) if use_database else None
    if db_engine is not None:
        preference_store = SqlPreferenceStore(db_engine)
        session_store = SqlSessionStore(db_engine)
        conversation_store = SqlConversationStore(db_engine)
        logger.info("持久化形态：%s", db_engine.url.get_backend_name())
    else:
        preference_store = JsonFilePreferenceStore(settings.data_dir)
        session_store = JsonFileSessionStore(settings.data_dir)
        conversation_store = JsonFileConversationStore(settings.data_dir)
        logger.info("持久化形态：本地 JSON 文件（DATABASE_URL=file）")

    # 旧版 file 订单无法按未知格式自动并账，必须先显式迁移。
    if not use_database:
        legacy_orders = settings.data_dir / "orders.json"
        if legacy_orders.exists() and legacy_orders.read_text().strip() not in {"", "[]", "{}"}:
            raise RuntimeError("检测到旧 orders.json，请先核对并迁移至交易账本，不能忽略历史订单后启动")
    # file 模式只影响会话和偏好；交易仍使用持久 SQLite 原子账本。
    trade_db_engine = db_engine or create_engine(f"sqlite+aiosqlite:///{settings.data_dir / 'trade.db'}")
    trade_store = SqlTradeStore(trade_db_engine)
    confirmations = ConfirmationService(product_repo, trade_store, bus=bus)

    # 工具熔断状态保存在当前进程内。
    circuit_registry = CircuitBreakerRegistry(
        failure_threshold=settings.tool_failure_threshold,
        reset_seconds=settings.tool_circuit_reset_seconds,
    )
    # 全进程唯一的网关配额闸门：三个 Agent 工厂共用，否则各限一份等于没限
    throttle = GatewayThrottle(
        max_concurrency=settings.llm_max_concurrency,
        min_interval_seconds=settings.llm_min_interval_seconds,
    )

    # ---- Application ----
    catalog_search = CatalogSearchUseCase(
        product_repo, embedder=embedder, vector_index=vector_index,
        hybrid_enabled=False,
        hybrid_lexical_weight=1.0,
        hybrid_vector_weight=1.0,
        recall_candidates=settings.recall_candidates,
    )
    place_order = PlaceOrderUseCase(confirmations)
    query_order = QueryOrderUseCase(trade_store)
    cancel_order = CancelOrderUseCase(confirmations)

    search_factory = SearchAgentFactory(
        settings, catalog_search, bus, knowledge_base, circuit_registry, throttle,
    )
    trade_factory = TradeAgentFactory(
        settings, place_order, query_order, cancel_order, bus, circuit_registry, throttle,
    )
    # 规范化事实与向量同库提交；默认长期记忆走语义检索。
    from app.infrastructure.semantic_memory import SemanticPreferenceStore, PreferenceDistiller
    from app.infrastructure.llm import create_chat_model
    preference_store = SemanticPreferenceStore(
        settings.data_dir / "buyer_memory.db", preference_store,
        PreferenceDistiller(create_chat_model(settings, stream=False, throttle=throttle, bus=bus)),
        embedder, settings.embedding_model + ":" + str(settings.embedding_dim),
    )
    preference_selector = preference_store
    from app.infrastructure.shopping_forms import ShoppingFormStore
    main_factory = MainAgentFactory(
        settings, search_factory, trade_factory, bus, preference_store, circuit_registry, throttle,
        preference_selector=preference_selector,
        buyer_skill_store=BuyerSkillStore(settings.data_dir / "buyer_skills.db"),
        shopping_form_store=ShoppingFormStore(settings.data_dir / "shopping_forms.db"),
    )
    sessions = SessionRegistry(main_factory, session_store, enforce_owner=settings.session_owner_binding)
    orchestrator = MainAgentOrchestrator(
        sessions, bus, preference_store, conversation_store,
        output_guard_enabled=settings.output_guard_enabled,
        token_budget_total=settings.token_budget_total,
        preference_selector=preference_selector,
        preference_top_k=settings.preference_top_k,
        evidence_store=search_factory.evidence_store,
        trade_state_provider=confirmations.agent_state,
    )

    from app.application.agents.context_service import ContextService
    return Container(
        settings=settings,
        bus=bus,
        orchestrator=orchestrator,
        context_service=ContextService(orchestrator, session_store, search_factory.evidence_store, confirmations, settings),
        query_order=query_order,
        cancel_order=cancel_order,
        product_repo=product_repo,
        embedder=embedder,
        vector_index=vector_index,
        knowledge_base=knowledge_base,
        db_engine=db_engine,
        confirmations=confirmations,
        trade_store=trade_store,
        trade_db_engine=trade_db_engine,
        runtime={"app_source_sha256": source_fingerprint},
        ag_ui_runtime=AGUIRuntime(AGUIJournal(settings.data_dir / "ag_ui_runs.db"), orchestrator, confirmations),
        session_store=session_store,
        identity_policy=identity_policy,
    )
