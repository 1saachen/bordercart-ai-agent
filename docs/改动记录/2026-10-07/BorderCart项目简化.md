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
- 前端真实浏览器验收和外部服务效果指标未知。
- 本地服务检查已完成：前端 `http://127.0.0.1:5173/` 返回 200；复用已有 API 进程 `http://127.0.0.1:8000/health` 返回 `status=ok`，SQLite 正常，Redis 和队列均为 disabled。第二个 API 进程因本地 Qdrant 目录锁按预期退出，未强制终止占用者。

## 关联版本

- 设计提交：`abff4a4 docs: 记录 BorderCart 项目简化设计`
- 实现提交：`ed4dcb8 refactor: simplify BorderCart local runtime`

本轮后续收缩改动（待提交）：公共 Registry 与 Personal Skill 解耦、Harness/reranker 默认关闭、Redis optional extra。
