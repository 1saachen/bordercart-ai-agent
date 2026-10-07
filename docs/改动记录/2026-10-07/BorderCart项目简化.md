# BorderCart AI 项目简化与前端改名

## 需求

将项目整理为适合跨境电商 AI Agent / LLM 工程岗位展示的最小闭环：保留 MainAgent、SearchAgent、TradeAgent 多 Agent 协作，商品 RAG、品类 KnowledgeBase RAG、Qdrant、Embedding 和 Personal Skill；收缩默认运行依赖；前端产品名改为 BorderCart AI（跨境智选助手）。

## 设计与实现

- 设计已记录在 [设计文档](../../superpowers/specs/2026-10-07-bordercart-simplification-design.md)，实施分支为 `codex/simplify-bordercart`。
- `app/infrastructure/settings.py` 将 `QUEUE_ENABLED`、`SEMANTIC_CACHE_ENABLED`、`QUEUE_PRIORITY_ENABLED` 的默认值改为关闭。配置 `REDIS_URL` 并显式打开变量时，旧 Redis/worker 路径仍可恢复。
- `app/presentation/server.py` 的 FastAPI 标题改为 `BorderCart AI 跨境智选助手`。
- `frontend/index.html`、`frontend/src/App.tsx`、`frontend/src/components/ContextWorkspace.tsx` 统一用户可见品牌；内部 storage key、API 字段、Python 包名和数据目录未改。
- `README.md` 与 `.env.example` 以 SQLite + 本地 Qdrant + 单进程 API 为默认路径，标明 Redis/worker、语义缓存和双队列为可选能力。
- 简化运行时默认关闭 `PROMPT_REGISTRY_ENABLED`、`PUBLIC_SKILLS_ENABLED`、`HARNESS_ENABLED` 和 `RERANKER_MODE`（`disabled`）；Personal Skill 仍由买家 SQLite 独立提供，公共 Registry 与高级 Harness 只在显式开启时装配。
- Redis Python 客户端从核心依赖移到 `redis` optional extra；本地模式不需要 Redis 客户端或 Redis 服务，启用 Redis 队列/缓存时使用 `uv sync --frozen --extra redis`。
- 新增 `tests/test_simplified_runtime.py` 覆盖本地默认配置和 Redis opt-in；新增 `frontend/tests/brand.test.ts` 覆盖品牌文案。
- 为 Windows 真实 Redis 回归补充平台适配：无 `AF_UNIX` 时使用隔离的本机随机 TCP 端口，并显式使用 RESP2；检测到 Redis 低于 6.2 时跳过依赖 `XAUTOCLAIM` 的队列测试。
- `app/application/usecases/catalog_search.py` 对关闭 reranker 时的向量候选按 `(-score, product_id)` 稳定排序，避免相同向量分数导致 Qdrant 内部顺序漂移。

## 验证

### 计划/实现

- 计划文件已保存；未对 AgentScope、商品 RAG、KnowledgeBase 或 Personal Skill 做大规模重写。
- 既有用户改动 `app/infrastructure/persistence/json_file_stores.py`、`tests/test_windows_file_store.py` 和 `eval/verification/startup-20261003/` 未覆盖。

### 回归测试

- `.venv/Scripts/python.exe -m pytest tests/test_simplified_runtime.py -q`：4 passed（含 Personal Skill/Registry、Harness、reranker 默认关闭断言）。
- 核心后端定向回归 `.venv/Scripts/python.exe -m pytest tests/test_runtime_distribution.py tests/test_simplified_runtime.py tests/test_buyer_workspace.py tests/test_buyer_skills.py tests/test_selected_skill.py tests/test_skill_catalog.py tests/test_knowledge_fixture.py tests/test_harness_middleware.py -q`：97 passed；同时修正 Compose 测试在 Windows 下显式按 UTF-8 读取文件。
- `npm test -- --run`（`frontend/`）：13 个测试文件、128 tests passed。
- `npm run build`（`frontend/`）：Vite production build 成功。
- `.venv/Scripts/python.exe -m pytest tests/test_simplified_runtime.py tests/test_reranker_client.py tests/test_retrieval.py -q`：16 passed；10 个已有检索 fixture 在 `data/catalog-v1.jsonl` 的 Windows 默认 GBK 读取阶段失败，错误为 `UnicodeDecodeError`，未进入本轮改动逻辑。该失败需要后续单独统一测试文件编码后复测。
- `.venv/Scripts/python.exe -m pytest -q`：`1276 passed, 1 skipped, 60 failed, 85 errors`。失败/错误主要来自既有 Windows 测试前提：UTF-8 数据和 YAML 被系统 GBK 读取、Redis 测试 fixture 硬编码 Unix `/tmp`、以及需要外部 Redis/模型链路；本轮未修改这些测试或数据文件，不能据此宣称全量回归通过。
- Windows Redis/队列定向回归：`15 passed, 43 skipped`。当前 `E:\Redis\redis-server.exe` 为 Redis 5.0.14，不支持项目所需的 `XAUTOCLAIM`；跳过发生在真实版本检测后。
- 最新隔离 API（端口 `18000`，独立临时数据目录）`GET /health`：`status=ok`、SQLite、本地模式、Redis/队列/语义缓存关闭，源码指纹为 `c3bf9fd0039f0cd877f42a4811c9903e873e921e3da843602cdb507c5c3f4578`。
- 最新隔离 API `POST /commerce/intents` 真实检索返回 `P1003`、`P1049` 等结构化商品卡和到手价；`GET /commerce/skills?buyer_id=verify-buyer` 返回买家隔离 Skill 列表（当前为空）。未记录密钥或完整买家原文。
- AG-UI journal 两个测试、eval feedback 两个测试仍失败；Harness Windows 文件权限/symlink 五个测试受系统差异影响，均未改成假通过。
- `pyproject.toml` 与 `uv.lock` 使用 Python `tomllib` 解析通过；当前环境没有 `uv`，且尝试安装时 pip 代理不可用，因此没有重新生成锁文件。

### 真实外部链路与效果验收

- 本轮未把单元测试通过写成模型、Embedding、Qdrant 或 KnowledgeBase 的生产效果结论。
- 前端页面的真实浏览器截图和完整外部模型链路未在本轮新增；此前启动证据保留在 [startup-20261003](../../../eval/verification/startup-20261003/)。
- 当前代码仍保留商品 RAG、KnowledgeBase 和 Personal Skill 实现，需在配置有效时按原启动流程做真实链路复测。

## 配置启停与回滚

- 本地默认：不配置 `REDIS_URL`，或使用 `QUEUE_ENABLED=0`；API 进程内直接处理请求。
- 启用旧队列：配置 `REDIS_URL`、`QUEUE_ENABLED=1`，需要 Redis 服务和单独 worker；语义缓存/双队列优先级分别由 `SEMANTIC_CACHE_ENABLED=1`、`QUEUE_PRIORITY_ENABLED=1` 控制。
- 回滚本轮默认行为：在 `.env` 显式设置旧变量值并重启 API；代码回滚使用本分支提交历史，不删除 `data/`。
- `.env` 中的真实密钥未写入本记录，测试使用假值 `test-key`。

## 未完成项

- 后端全量回归存在上述环境相关失败，完整 AgentScope/KnowledgeBase 测试仍需要统一 UTF-8/临时目录兼容并准备有效模型、Redis 和 Qdrant 条件。
- Redis/worker 兼容路径本轮只做默认关闭和文档整理，未删除历史模块。
- Compose 仍保留 Redis、worker 和 Qdrant 多容器编排作为高级部署入口；本轮只收缩其默认应用配置，不把该模式作为本地最小启动前置条件。
- 前端浏览器验收已确认 BorderCart AI 品牌、商品卡和 Personal Skill 页面可见；外部服务效果指标未知。
- 本地服务检查已完成：前端 `http://127.0.0.1:5173/` 返回 200；隔离 API `http://127.0.0.1:18000/health` 使用当前源码并完成真实商品检索。未强制终止用户已有 API 进程。

## 关联版本

- 设计提交：`abff4a4 docs: 记录 BorderCart 项目简化设计`
- 实现提交：`ed4dcb8 refactor: simplify BorderCart local runtime`

后续收缩改动已提交于 `1f6ad4a refactor: make BorderCart core runtime opt-in`；本轮 Windows Redis fixture 兼容和稳定排序修复待提交。
