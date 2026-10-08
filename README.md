# BorderCart AI

BorderCart AI 是一个面向跨境电商选品与下单确认的多 Agent 示例项目。核心链路是 `MainAgent` 协作调度 `SearchAgent` 和 `TradeAgent`，商品检索使用 BM25 + Embedding/Qdrant 双路召回与 RRF 融合，品类问题使用 AgentScope `KnowledgeBase`，买家可以创建只属于自己的 Personal Skill。

## 核心能力

- 多 Agent 协作：MainAgent、SearchAgent、TradeAgent。
- 商品 RAG：BM25 关键词检索与 Qdrant 向量检索双路召回，使用 RRF 融合排名，按买家条件过滤并读取权威库存。
- 品类 KnowledgeBase：从 Markdown 知识构建 AgentScope KnowledgeBase，回答选购常识。
- Personal Skill：买家创建、读取、删除和注入自己的 Markdown 选购流程，按买家隔离。
- 交易确认：订单创建、取消、库存扣减和幂等记录使用 SQLite 事务；模型不能绕过页面确认。
- 会话恢复：会话、消息、运行事件和确认状态持久化，刷新页面后可以继续查看。
- 单进程本地运行：FastAPI + AG-UI/SSE 后端，React + Vite 前端，Qdrant 可使用本地落盘模式。

## 技术栈

| 层次 | 技术 | 用途 |
| --- | --- | --- |
| Agent | AgentScope 2.0.8 | Agent、工具调用、子 Agent 协作、KnowledgeBase |
| 后端 | Python、FastAPI、Uvicorn | API、会话、交易和流式运行 |
| 检索 | BM25、OpenAI-compatible Embedding、Qdrant、RRF | 商品混合召回、融合排名和条件过滤 |
| 持久化 | SQLite、本地文件 | 会话、偏好、Personal Skill、订单、库存 |
| 前端 | React、TypeScript、Vite | 对话、商品卡、Skill 和确认页面 |
| 协议 | AG-UI、SSE、A2UI | 文本、工具结果和运行状态流 |

## 快速开始

环境要求：Python 3.11-3.13、Node.js 20+、npm，以及一个支持工具调用和流式输出的 OpenAI-compatible 模型服务。

```bash
uv sync
npm --prefix frontend ci
cp .env.example .env
```

编辑 `.env`，至少填写 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 和可用的 `EMBEDDING_MODEL`。也可以把已有的 `deepseekapi` 环境变量映射为 `LLM_API_KEY`，不要把真实密钥提交到 Git。

启动后端：

```bash
uv run python -m uvicorn app.presentation.server:app --host 127.0.0.1 --port 8000 --workers 1
```

启动前端：

```bash
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

打开 <http://127.0.0.1:5173>，可以用“帮我找一个预算 300 元以内、寄到中国的轻便背包”开始一次检索。健康接口为 <http://127.0.0.1:8000/health>，API 文档为 <http://127.0.0.1:8000/docs>。

首次启动会加载样例商品、创建 SQLite 表、建立 Qdrant 商品向量索引并初始化品类 KnowledgeBase。商品检索使用 BM25 + Qdrant 双路召回，先做结构化硬过滤，再经 RRF 融合、同款去重后返回 Top-K；当前不使用 Reranker。向量服务不可用时自动降级为 BM25。`QDRANT_URL` 留空时，向量数据落在 `DATA_DIR/qdrant`；设置服务端地址后可切换到 Qdrant 服务。

## Docker Compose

Compose 只包含 API、Qdrant 和前端：

```bash
docker compose --env-file .env -f docker/docker-compose.yaml up -d --build
```

访问 <http://127.0.0.1:5173>。容器数据保存在 `app-data` 和 `qdrant-data` 卷中。

## 配置

配置字段和默认值见 [.env.example](.env.example)。常用字段：`LLM_*` 聊天模型、`EMBEDDING_*` 向量模型、`HYBRID_*`/`RECALL_CANDIDATES` 商品混合召回、`QDRANT_*` 商品索引、`CATEGORY_KB_COLLECTION` 品类知识、`DATA_DIR`/`DATABASE_URL` 本地数据、`PREFERENCE_*` 偏好注入、`IDENTITY_*` 演示身份。

启用商品混合检索需设置 `HYBRID_RECALL_ENABLED=1`，并配置可用的 `EMBEDDING_*`。BM25 与向量召回权重默认均为 1，召回候选数量默认 32。当前保持 `RERANKER_BASE_URL` 为空，无需配置精排服务。

配置变更后重启后端。正常双路召回的工具结果标注 `recall_strategy=hybrid_rrf`；向量异常时为 `bm25`。精确商品/SKU ID 查询仍直接核对商品目录，不走模糊检索。

`.env` 已被 Git 忽略。不要提交密钥、真实数据库、买家原文或运行数据。

## 项目结构

```text
app/application/agents/       MainAgent、SearchAgent、TradeAgent
app/application/tools/        商品、KnowledgeBase、Skill、交易工具
app/infrastructure/rag/       AgentScope KnowledgeBase
app/infrastructure/vector/    Qdrant 商品索引
app/infrastructure/persistence/ SQLite 与本地文件存储
app/presentation/             FastAPI、AG-UI/SSE
frontend/                     React/Vite 页面
tests/                        核心运行时和业务回归测试
data/                         本地运行数据（不提交）
```

## 简历描述

> BorderCart AI：基于 AgentScope 搭建跨境电商多 Agent 选品助手。设计 MainAgent 调度 SearchAgent/TradeAgent 的协作架构，使用 BM25 与 Qdrant 双路召回、RRF 融合及结构化条件过滤实现商品 RAG，并接入 KnowledgeBase 处理品类知识问答；实现 Personal Skill 的买家隔离、会话恢复、交易确认及 SQLite 订单库存事务，通过 FastAPI/AG-UI/SSE 与 React 前端完成端到端交互。

## 限制

项目使用样例商品、演示身份和本地订单账本，不接入真实支付、物流或电商供给。上线前需要独立完成账号、库存、支付、物流和模型服务的安全与效果验证。
