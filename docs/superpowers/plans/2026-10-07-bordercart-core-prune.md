# BorderCart AI 核心版硬裁剪实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 把 BorderCart AI 从“默认关闭扩展”收缩为只包含多 Agent、商品 RAG、KnowledgeBase RAG、Personal Skill 和本地单进程 API 的可发布核心版。

**Architecture:** 以 `app/composition.py` 为唯一装配边界，移除 Redis、worker、Registry、Harness、reranker、Tavily 和外部 tracing 的构造路径；保留进程内事件总线、SQLite、Qdrant、Embedding、AgentScope KnowledgeBase 与 AG-UI。随后同步删除无调用方的扩展模块、配置、依赖、脚本、测试和 Compose 文档，并以核心回归和当前源码隔离实例验收。

**Tech Stack:** Python 3.11–3.13、AgentScope 2.0.8、FastAPI、AG-UI/SSE、SQLite、Qdrant、OpenAI-compatible Embedding、React 18、TypeScript、Vite、pytest、Vitest。

---

## 保护范围

以下用户已有未提交内容不能修改、暂存或提交：

- `app/infrastructure/persistence/json_file_stores.py`
- `tests/test_windows_file_store.py`
- `eval/verification/startup-20261003/`
- `frontend/tsconfig.tsbuildinfo`
- `.env`

GitHub 发布目标是 `bordercart` remote 的公开仓库 `1saachen/bordercart-ai-agent`，只做普通 fast-forward push。

## 文件地图

核心实现：`app/composition.py`、`app/infrastructure/settings.py`、`app/presentation/server.py`、`app/presentation/ag_ui*.py`、`app/application/agents/`、`app/application/tools/{product_search_tool,category_insight_tool,task_dispatch_tool,capability_tools}.py`、`app/infrastructure/{eventbus,resilience,throttle}.py`、`app/infrastructure/rag/`、`app/infrastructure/vector/`、`app/infrastructure/embedding/`、`app/infrastructure/buyer_skills.py`。

删除候选：`app/worker.py`、`app/domain/queue/`、`app/infrastructure/{queue,cache,rerank}/`、共享 Redis 实现、`langfuse_config.py`、`tracing.py`、Capability/Prompt Registry、Harness、`web_search_tool.py`，以及只服务这些模块的 scripts/tests。删除每个候选前必须用 `rg` 确认没有核心引用。

## Task 1: 锁定核心行为

**Files:** `tests/test_core_runtime.py`（创建）、`tests/test_simplified_runtime.py`、核心 Agent/RAG/Skill 测试。

- [ ] **Step 1: 写核心装配测试**

使用临时 `DATA_DIR`、假 `LLM_API_KEY` 和现有 fake fixture，断言 `build_container()` 能创建 `knowledge_base`、`vector_index`、SearchAgent、TradeAgent 和买家 `BuyerSkillStore`，且没有 Redis/队列/公共 Registry 依赖。

- [ ] **Step 2: 运行基线**

```powershell
$env:PYTHONUTF8='1'
.venv\Scripts\python.exe -m pytest tests/test_core_runtime.py tests/test_simplified_runtime.py -q --tb=short
```

记录旧装配中仍暴露的扩展字段和导入错误。

- [ ] **Step 3: 提交测试边界**

```powershell
git add tests/test_core_runtime.py tests/test_simplified_runtime.py
git commit -m "test: lock BorderCart core runtime boundary"
```

## Task 2: 固定本地单进程组合根

**Files:** `app/infrastructure/settings.py`、`app/composition.py`、`app/presentation/server.py`、`app/presentation/ag_ui_runtime.py`、`app/infrastructure/eventbus.py`、核心 API 测试。

- [ ] **Step 1: 收缩 Settings**：删除 Redis、队列、语义缓存、Prompt/Capability Registry、Harness、reranker、Tavily、OTLP、Langfuse 字段和环境变量读取；保留模型、Embedding、Qdrant、SQLite、身份、上下文、熔断和本地限流配置。
- [ ] **Step 2: 收缩 composition**：固定 `cache=None`、`semantic_cache=None`、`task_queue=None`、`backplane=None`、`prompt_registry=None`、`reranker=None`；直接创建 OpenAI Embedding、本地 CircuitBreaker、GatewayThrottle、三个 Agent 工厂、KnowledgeBase、BuyerSkillStore 和 AG-UI runtime。
- [ ] **Step 3: 清理 Container 和健康接口**：移除扩展字段及 shutdown 调用；`/health` 只返回 `status`、模型、SQLite/交易库、Qdrant 和源码指纹。
- [ ] **Step 4: 回归并提交**：运行核心 API/AG-UI/确认测试后提交 `refactor: make BorderCart runtime core-only`。

## Task 3: 保留三 Agent、RAG 和 Personal Skill

**Files:** `app/application/agents/`、`app/application/tools/`、`app/infrastructure/rag/`、`app/infrastructure/buyer_skills.py`；删除 Harness、Registry、reranker、Tavily 模块。

- [ ] **Step 1: 收缩 MainAgent/Orchestrator**：删除 Sequencing/Loop/Drift、SemanticCache、Prompt/Capability contract 和 tracing 分支；保留本地 resilience、Skill preload、确认、候选投影、恢复和 AG-UI 事件。
- [ ] **Step 2: 固定工具集**：SearchAgent 只注册商品、品类 KnowledgeBase 和事实查询；TradeAgent 只注册订单工具；`task_dispatch` 继续创建隔离 SearchAgent/TradeAgent 并注入买家偏好；商品检索固定无 reranker。
- [ ] **Step 3: 解耦 Skill**：`selected_skill.py`、`personal_skill_context.py` 和 `capability_tools.py` 只依赖 BuyerSkillStore 的 owner/version/hash 校验，删除公共 Registry 工具。
- [ ] **Step 4: 删除无调用方文件并回归**：先运行子 Agent、KnowledgeBase、Skill 和 workspace 测试，再用 `rg` 确认核心源码没有扩展导入，最后提交 `refactor: keep BorderCart agents focused on core flows`。

## Task 4: 删除基础设施扩展和专用脚本

**Files:** 删除 `app/worker.py`、queue/cache/rerank、共享 Redis、Langfuse/OTel/tracing、扩展专用 scripts 和 `scripts/eval/harness/`；修改 `eventbus.py`、`resilience.py`、`throttle.py`、`llm.py`。

- [ ] **Step 1: 固定进程内 EventBus**：删除 backplane、Redis publish 和 tracing correlation 分支，只保留进程内订阅/发布。
- [ ] **Step 2: 保留本地可靠性**：保留 CircuitBreakerRegistry、ToolResilienceMiddleware、GatewayThrottle，删除 Redis 共享版本和外部 tracing attributes。
- [ ] **Step 3: 导入与回归**：运行 `python -m compileall -q app scripts` 及 EventBus、resilience、throttle、core runtime 测试。
- [ ] **Step 4: 提交**：`git commit -m "refactor: remove optional infrastructure extensions"`。

## Task 5: 清理依赖、配置、Compose 和 README

**Files:** `pyproject.toml`、`uv.lock`、`.env.example`、`.dockerignore`、`README.md`、`docker/`、当日改动记录和分布测试。

- [ ] **Step 1: 清理依赖**：删除 Redis、OpenTelemetry/OTLP 和无核心调用的 optional extras；用 `tomllib` 验证两个 TOML 文件，若没有 uv 明确记录无法重锁。
- [ ] **Step 2: 重写 `.env.example`**：只保留模型、Embedding、DATA_DIR、DATABASE_URL、QDRANT、身份、上下文、核心超时/熔断和端口。
- [ ] **Step 3: 删除高级 Compose/Nginx**：README 只保留单 API、单 Vite、本地 Qdrant 启动步骤。
- [ ] **Step 4: 重写 README**：只描述项目定位、核心架构、三 Agent、商品 RAG、KnowledgeBase、Personal Skill、环境变量、启动命令、页面/API、限制和简历描述；不得出现扩展名词或可选扩展章节。
- [ ] **Step 5: 静态回归**：`rg` 检查核心源码、配置、README、Docker 不命中删除清单，并运行 runtime distribution/simplified tests；提交 `docs: publish BorderCart core-only project`。

## Task 6: 全量验证和 GitHub 发布

**Files:** 新建 `eval/verification/bordercart-core-prune-20261007/` 的 README、health JSON、runtime-chain JSON、测试输出；更新当日改动记录。

- [ ] **Step 1: 静态与导入**：运行 `compileall`、TOML 解析和 `git diff --check`。
- [ ] **Step 2: 全量回归**：运行后端 pytest、前端 Vitest 和生产构建，保存原始输出。
- [ ] **Step 3: 当前源码隔离 API**：用独立 `DATA_DIR`/`18000` 启动，等待商品和知识索引完成；`/health` 指纹必须与工作树一致，健康 JSON 不含扩展状态。
- [ ] **Step 4: 真实核心链路**：记录商品 ID/到手价、商品 AG-UI 的 `product_search_tool`、品类 AG-UI 的 `category_insight_tool`、Skill 创建/读取/跨买家隔离/删除和浏览器品牌入口。
- [ ] **Step 5: 发布核对**：确认 `.env`、用户未提交文件和真实数据库不在提交中，普通 push 到 `bordercart`，远端 SHA 与本地 HEAD 一致。
- [ ] **Step 6: 最终记录**：当日记录写明删除清单、测试统计、源码指纹、GitHub URL 和保护文件；最终状态只能显示用户原有文件。

## 计划自审

- 设计保留边界由 Task 1–3 和 Task 6 的测试/真实链路覆盖。
- 删除边界由 Task 3–5 覆盖，每组删除前都有 `rg`、compile/import 或核心测试门槛。
- 配置、依赖、README、Compose 和 GitHub 发布由 Task 5–6 覆盖。
- `.env`、Windows 文件存储改动和启动历史证据明确列入保护范围。
- 计划没有删除 Git 历史，回滚通过历史提交完成。
