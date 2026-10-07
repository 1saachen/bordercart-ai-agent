# BorderCart AI 核心版硬裁剪设计

## 状态

- 需求已由用户确认：代码和 GitHub 仓库都裁剪为真正的简化版。
- 目标仓库：`https://github.com/1saachen/bordercart-ai-agent`。
- 现有用户未提交文件不属于本次裁剪范围，必须原样保留：
  - `app/infrastructure/persistence/json_file_stores.py`
  - `tests/test_windows_file_store.py`
  - `eval/verification/startup-20261003/`
  - `frontend/tsconfig.tsbuildinfo`

## 目标

将仓库收缩为适合简历展示和本地演示的跨境电商 Agent 核心闭环。仓库只保留多 Agent 协作、商品 RAG、品类 KnowledgeBase RAG、Personal Skill、交易确认和本地单进程运行；删除可选扩展的代码、配置、依赖、脚本、测试和文档入口。

Git 历史仍保留被删除代码，因此裁剪是当前分支和 GitHub `main` 的发布形态变化，不要求销毁历史提交。

## 保留边界

### 运行时核心

- `MainAgent -> SearchAgent / TradeAgent` 的 AgentScope 协作和 `task_dispatch`。
- FastAPI、Uvicorn、AG-UI/SSE、React、TypeScript、Vite。
- SQLite 会话、事件、订单、库存、确认单、偏好和买家 Personal Skill。
- 商品 Embedding、Qdrant 本地向量索引、应用层商品过滤/补召回和稳定向量排序。
- AgentScope `KnowledgeBase`、Markdown 品类知识和 Qdrant 知识索引。
- 本地事件总线、运行恢复、确认流程、熔断/超时和本地网关限流。
- 前端商品卡、对话、Skill 编辑、偏好、订单和运行恢复页面。

### 配置核心

只保留：

- `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`。
- `EMBEDDING_BASE_URL`、`EMBEDDING_API_KEY`、`EMBEDDING_MODEL`、`EMBEDDING_DIM`。
- `DATA_DIR`、`DATABASE_URL`、`QDRANT_URL`、`QDRANT_COLLECTION`。
- `PORT`、`LOG_LEVEL`、CORS/身份和核心上下文预算配置。

Embedding 默认复用聊天模型网关和密钥。`QDRANT_URL` 为空时使用本地 `DATA_DIR/qdrant`；不引入 Redis、云端追踪或其他服务作为启动前置条件。

## 删除边界

### 代码和依赖

删除或移除核心装配引用：

- Redis 客户端、Redis Cache、Redis Stream 队列、队列 archive/maintenance、跨进程 event backplane、`app/worker.py`。
- 语义缓存、Embedding 缓存和 Redis 共享熔断/限流实现。
- Prompt Registry、Prompt release、Capability Registry、公共 Skill 审核/发布工具。
- Harness、Loop/Drift 检测和评测专用运行护栏。
- HTTP reranker、reranker factory/client、Tavily Web Search。
- Langfuse 配置、OpenTelemetry/OTLP tracing 和外部 feedback 上传。
- 高级 Docker Compose 多容器部署、Nginx 反向代理专用入口。

保留本地 `TradeEventBus`，但移除其 tracing/backplane 依赖；事件只在单进程内供 AG-UI 和运行记录使用。

### 配置和依赖

- 从 `Settings`、`.env.example`、健康接口和 README 删除被裁剪能力的配置项。
- 从 `pyproject.toml` 删除 Redis、OpenTelemetry、PyJWT（若身份简化后不再使用）及只服务于已删除扩展的依赖；保留实际核心依赖并同步 `uv.lock`。
- 不保留 `redis`、`retrieval`、`optimization` 这些与简化运行无关的 optional extra；若 `fastembed` 仍无核心调用则一并删除其 extra。

### 文档、脚本和测试

- README 只描述核心架构、环境变量、本地启动、核心 API 和简历可展示能力。
- `.env.example` 不再出现 Redis、worker、Registry、Harness、reranker、Tavily、Langfuse、OTLP 或 Docker Compose 配置。
- 删除只覆盖已删除扩展的脚本和测试；保留核心 Agent、RAG、KnowledgeBase、Skill、确认、API、前端和本地启动测试。
- 改动记录不再把删除的扩展写成可恢复运行路径；历史验证文件保留，但明确它们属于裁剪前历史证据。

## 运行数据流

1. API 启动时读取模型、Embedding、SQLite 和 Qdrant 配置。
2. 组合根创建本地事件总线、商品索引、KnowledgeBase、SQLite stores、三个 Agent 工厂和 AG-UI runtime。
3. 首次启动同步商品向量和品类知识；不创建 Redis 客户端、worker 或外部 tracing provider。
4. 请求进入 MainAgent；简单问题直接使用 SearchAgent/TradeAgent 共享工具，复杂问题经 `task_dispatch` 创建隔离子 Agent。
5. SearchAgent 按问题选择商品 `product_search_tool` 或品类 `category_insight_tool`；Personal Skill 从买家 SQLite 读取并按需注入。
6. 交易工具只生成并等待确认凭证，确认后由 SQLite 事务执行订单和库存变更。
7. AG-UI 通过进程内事件总线和持久运行日志向前端流式返回状态、文本和结构化商品数据。

## 配置迁移和回滚

- 旧 `.env` 中的 Redis、Registry、Harness、reranker、Tavily、Langfuse 等变量会被忽略；文档提示删除这些变量，避免产生“开关仍然有效”的误解。
- `DATABASE_URL=file` 的用户文件存储路径仍保留，Windows 兼容改动不参与裁剪。
- 回滚通过 Git 历史恢复裁剪前提交，不在当前简化版重新引入隐式兼容分支。
- 不删除用户现有 `data/`；若旧数据包含队列、缓存或 Registry 数据，简化版不读取这些表/文件。

## 验证门槛

### 静态门槛

- `rg` 检查核心源码、README、`.env.example` 和 `pyproject.toml` 不再出现已删除扩展的运行时入口或配置。
- `python -m compileall app scripts` 和 `tomllib` 解析 `pyproject.toml`、`uv.lock` 成功。
- `git diff --check` 成功，且 `.env`、用户未提交文件不在发布提交中。

### 功能门槛

- 核心后端测试通过：默认单进程、MainAgent 调度、SearchAgent/TradeAgent、商品 RAG、KnowledgeBase、Personal Skill、确认和 API。
- 前端 Vitest 和生产构建通过。
- 当前源码隔离 API `/health` 返回 SQLite、本地 Qdrant、Redis 不存在/不需要，且源码指纹与工作树一致。
- 真实 AG-UI 商品问题触发 `product_search_tool`；品类问题触发 `category_insight_tool`；Personal Skill 完成创建、同买家读取、跨买家隔离和删除。
- 浏览器首页显示 BorderCart AI 品牌，Personal Skill 页面可见且可编辑。

## 风险与取舍

- 删除后不再支持 Redis worker、云端追踪、公共 Skill 发布和 HTTP reranker；这些能力只能从 Git 历史恢复。
- 本地单进程不提供跨进程任务削峰，适合演示和简历项目，不作为生产部署方案。
- 商品排序保留 Embedding/本地过滤和稳定排序，不宣称 reranker 或线上检索效果。
- 外部模型、Embedding 和 Qdrant 真实效果仍按环境记录，不用单元测试替代效果结论。
