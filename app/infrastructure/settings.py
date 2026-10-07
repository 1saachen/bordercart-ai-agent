# -*- coding: utf-8 -*-
"""settings

从 .env / 环境变量读取全部配置，Infrastructure 之外不允许直接触碰 os.environ。

二期增量：embedding / Qdrant / Reranker / Tavily / OTLP / 数据目录。
三期增量：品类知识库 collection、Context 工程（压缩阈值/结果截断/Token 预算）、工具超时与熔断、CORS。
四期增量：模型回退与网关配额闸门（并发上限/请求间隔/重试次数）。
可选能力全部按"空值即关闭/降级"设计，保证零外部依赖也能启动。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# 项目根目录（globex-agent/）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

def _load_environment(path: Path) -> None:
    load_dotenv(path)


_load_environment(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    llm_base_url: str
    llm_api_key: str = field(repr=False)
    llm_model: str
    port: int
    log_level: str
    # ---- 检索升级（模块一）----
    embedding_base_url: str
    embedding_api_key: str = field(repr=False)
    embedding_model: str
    embedding_dim: int  # 知识库建库需显式维度（text-embedding-v4 实测 1024）
    qdrant_url: str  # 空 = qdrant-client 本地嵌入模式（DATA_DIR/qdrant）
    qdrant_collection: str
    # ---- 数据目录（模块三）----
    data_dir: Path
    # ---- 三期：品类知识库 ----
    category_kb_collection: str
    # ---- 三期：Context 工程 ----
    context_size: int  # 模型上下文窗口，压缩阈值按此比例计算
    tool_result_limit: int  # 单个工具结果 token 上限（AgentScope 2.0.8 口径）
    reply_token_budget: int  # 0 = 不启用 Token 预算护栏
    # ---- 三期：工具韧性 ----
    tool_failure_threshold: int  # 连续失败达阈值后熔断
    tool_circuit_reset_seconds: float  # 熔断后多久转半开探测
    # ---- 三期：前端 ----
    cors_origins: list[str]
    # ---- 四期：模型回退与网关配额闸门 ----
    # 这组给默认值：前面几期每次扩字段都会打断测试里手工构造的 Settings，
    # 新增可选配置一律带默认值，避免同样的修改成本反复发生。
    llm_fallback_model: str = ""  # 空 = 不回退，重试用尽直接报错
    llm_max_concurrency: int = 2  # 同时在飞的模型请求上限
    llm_min_interval_seconds: float = 1.0  # 相邻请求起跑最小间隔，治速率爬升过快
    llm_max_retries: int = 2  # 瞬时故障重试次数（指数退避）
    prompt_cache_mode: str = "passthrough"
    prompt_cache_policy: str = "static"
    skill_catalog_mode: str = "legacy"  # append_only 为变化驱动候选，收益验收后再启用
    # ---- 四期：存储 ----
    # 默认 SQLite（零外部依赖，落在 DATA_DIR/globex.db）。
    # 换服务型数据库需自行装异步驱动（aiomysql / asyncpg）并改此 URL，本仓未验证。
    # 特殊值 "file" = 退回三期的 JSON 文件存储（无数据库）
    context_strategy: str = "legacy"
    context_pruning_timing: str = "after_use"
    context_product_tokens: int = 6000
    context_prompt_layout: str = "legacy_system"  # stable_prefix 待收益验收后启用
    context_state_mode: str = "snapshot"  # delta 只用于稳定前缀的独立实验
    context_prune_low_ratio: float = 1.0  # 小于 1 时触发后回收到较低水位
    context_lookup_mode: str = "strict"  # bounded 兼容明确字段别名及限额分页
    context_compact_result_rules: bool = False  # 固定说明提升到规则，JSON只移除空白
    context_target_tokens: int = 48000
    database_url: str = ""
    output_guard_enabled: bool = True  # L4 输出审核（纯正则）
    token_budget_total: int = 0  # 0 = 不启用请求级 Token 预算与四档降级
    # 长期记忆：偏好注入策略
    preference_relevance_enabled: bool = False  # 向量相关性筛选，每轮多一次 embedding，默认关
    preference_top_k: int = 5  # like 注入上限；dislike（黑名单）不受此限
    preference_subagent_inject: bool = True  # 给检索子 Agent 注入偏好（纯本地拼装，零成本）
    session_owner_binding: bool = True
    identity_mode: str = "demo"
    metrics_reader_buyers: tuple[str, ...] = ()
    identity_hmac_secret: str = field(default="", repr=False)
    recall_candidates: int = 32
    embedding_version: str = ""  # 同名模型更新权重或编码方式时，用版本区分已存向量


def load_settings() -> Settings:
    llm_base_url = os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    llm_api_key = os.getenv("LLM_API_KEY", "")
    if not llm_api_key:
        raise RuntimeError(
            "未配置 LLM_API_KEY，无法启动。请通过环境变量注入（推荐）："
            "export LLM_API_KEY=<你的密钥>；或在项目根目录创建本地 .env 文件"
            "（参考 .env.example，该文件已被 gitignore，不会入库）。"
        )
    data_dir = Path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "data")))
    data_dir.mkdir(parents=True, exist_ok=True)  # SQLite 默认落在此目录，建库前必须存在
    return Settings(
        context_strategy=os.getenv("CONTEXT_STRATEGY", "legacy"),
        skill_catalog_mode=os.getenv("SKILL_CATALOG_MODE", "legacy"),
        context_pruning_timing=os.getenv("CONTEXT_PRUNING_TIMING", "after_use"),
        context_product_tokens=int(os.getenv("CONTEXT_PRODUCT_TOKENS", "6000")),
        context_prompt_layout=os.getenv("CONTEXT_PROMPT_LAYOUT", "legacy_system"),
        context_state_mode=os.getenv("CONTEXT_STATE_MODE", "snapshot"),
        context_prune_low_ratio=float(os.getenv("CONTEXT_PRUNE_LOW_RATIO", "1")),
        context_lookup_mode=os.getenv("CONTEXT_LOOKUP_MODE", "strict"),
        context_compact_result_rules=os.getenv("CONTEXT_COMPACT_RESULT_RULES", "0") == "1",
        context_target_tokens=int(os.getenv("CONTEXT_TARGET_TOKENS", "48000")),
        llm_base_url=llm_base_url,
        llm_api_key=llm_api_key,
        llm_model=os.getenv("LLM_MODEL", "qwen3-max"),
        recall_candidates=int(os.getenv("RECALL_CANDIDATES", "32")),
        port=int(os.getenv("PORT", "8000")),
        log_level=os.getenv("LOG_LEVEL", "info"),
        # embedding 默认复用 LLM 网关（OpenAI 兼容 /v1/embeddings）
        embedding_base_url=os.getenv("EMBEDDING_BASE_URL") or llm_base_url,
        embedding_api_key=os.getenv("EMBEDDING_API_KEY") or llm_api_key,
        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-v4"),
        embedding_version=os.getenv("EMBEDDING_VERSION", ""),
        embedding_dim=int(os.getenv("EMBEDDING_DIM", "1024")),
        qdrant_url=os.getenv("QDRANT_URL", ""),
        qdrant_collection=os.getenv("QDRANT_COLLECTION", "globex_products"),
        data_dir=data_dir,
        category_kb_collection=os.getenv("CATEGORY_KB_COLLECTION", "globex_category_kb"),
        context_size=int(os.getenv("CONTEXT_SIZE", "128000")),
        tool_result_limit=int(os.getenv("TOOL_RESULT_LIMIT", "20000")),
        reply_token_budget=int(os.getenv("REPLY_TOKEN_BUDGET", "0")),
        tool_failure_threshold=int(os.getenv("TOOL_FAILURE_THRESHOLD", "3")),
        tool_circuit_reset_seconds=float(os.getenv("TOOL_CIRCUIT_RESET_SECONDS", "60")),
        cors_origins=[
            origin.strip()
            for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
            if origin.strip()
        ],
        # 实测 qwen3.7-plus 配额池极紧（单发一条也可能 429），默认配上备用模型保底，
        # 重试用尽后自动回退并发 model.fallback 事件，不静默降级
        llm_fallback_model=os.getenv("LLM_FALLBACK_MODEL", "qwen-plus"),
        # 默认 2 而不是 1：三期真并行 fork 实测 1.84x 加速，设 1 会把并行收益完全抹掉
        llm_max_concurrency=int(os.getenv("LLM_MAX_CONCURRENCY", "2")),
        llm_min_interval_seconds=float(os.getenv("LLM_MIN_INTERVAL_SECONDS", "1.0")),
        llm_max_retries=int(os.getenv("LLM_MAX_RETRIES", "2")),
        prompt_cache_mode=os.getenv("PROMPT_CACHE_MODE", "passthrough"),
        prompt_cache_policy=os.getenv("PROMPT_CACHE_POLICY", "static"),
        # 兼容早期变量名 MYSQL_URL；两者都没配时默认本地 SQLite
        database_url=(
            os.getenv("DATABASE_URL")
            or os.getenv("MYSQL_URL")
            or f"sqlite+aiosqlite:///{data_dir / 'globex.db'}"
        ),
        output_guard_enabled=os.getenv("OUTPUT_GUARD_ENABLED", "1") not in ("0", "false", "False"),
        token_budget_total=int(os.getenv("TOKEN_BUDGET_TOTAL", "0")),
        preference_relevance_enabled=os.getenv("PREFERENCE_RELEVANCE_ENABLED", "0")
        not in ("0", "false", "False"),
        preference_top_k=int(os.getenv("PREFERENCE_TOP_K", "5")),
        preference_subagent_inject=os.getenv("PREFERENCE_SUBAGENT_INJECT", "1")
        not in ("0", "false", "False"),
        session_owner_binding=os.getenv("SESSION_OWNER_BINDING", "1") not in ("0", "false", "False"),
        identity_mode=os.getenv("IDENTITY_MODE", "demo"),
        metrics_reader_buyers=tuple(item.strip() for item in os.getenv("METRICS_READER_BUYERS", "").split(",") if item.strip()),
        identity_hmac_secret=os.getenv("IDENTITY_HMAC_SECRET", ""),
    )
