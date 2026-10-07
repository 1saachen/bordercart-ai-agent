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
- Windows 全量回归需先设置 `$env:PYTHONUTF8='1'`（仓库中的 UTF-8 fixture 在未设置时会被 Windows 默认 GBK 误读）；`.venv/Scripts/python.exe -m pytest -q --tb=short`：`1379 passed, 47 skipped, 1 warning`。原始统计见 [pytest-full-current.txt](../../../eval/verification/bordercart-simplification-20261007/pytest-full-current.txt)。跳过项来自当前 Redis 5.0 不支持 `XAUTOCLAIM`、Windows 账户没有创建 symlink 的特权，以及 Windows ACL 不由 `st_mode` 表示的权限断言；没有失败或错误。
- Windows Redis/队列定向回归：`15 passed, 43 skipped`。当前 `E:\Redis\redis-server.exe` 为 Redis 5.0.14，不支持项目所需的 `XAUTOCLAIM`；跳过发生在真实版本检测后。
- AG-UI、eval feedback、Harness 本机兼容和 Langfuse 本机 HTTP fixture 定向回归：`108 passed, 3 skipped`；新增修复覆盖 SQLite 短租约、回环 HTTP 绕过系统代理、跨平台 evidence 链接和 Windows 权限语义。
- 当前源码隔离 API（端口 `18000`，独立临时数据目录）的健康检查和真实链路结果见 [health-current.json](../../../eval/verification/bordercart-simplification-20261007/health-current.json) 与 [runtime-chain-current.json](../../../eval/verification/bordercart-simplification-20261007/runtime-chain-current.json)。证据只保留状态、源码指纹和布尔检查，不记录密钥、Skill 正文或买家原文。
- Langfuse 云端真实链路仍未验收：当前网络对外服务返回 `502`，该限制与本地 Langfuse HTTP fixture 测试分开记录，不影响本地代码回归结论。
- `pyproject.toml` 与 `uv.lock` 使用 Python `tomllib` 解析通过；当前环境没有 `uv`，且尝试安装时 pip 代理不可用，因此没有重新生成锁文件。

### 真实外部链路与效果验收

- 本轮未把单元测试通过写成模型、Embedding、Qdrant 或 KnowledgeBase 的生产效果结论。
- 前端页面的真实浏览器截图和完整外部模型链路未在本轮新增；此前启动证据保留在 [startup-20261003](../../../eval/verification/startup-20261003/)。本轮原始验证目录见 [bordercart-simplification-20261007](../../../eval/verification/bordercart-simplification-20261007/README.md)。
- 当前源码隔离实例已按有效配置完成商品 RAG、KnowledgeBase 和 Personal Skill 真实链路复测；证据见 [runtime-chain-current.json](../../../eval/verification/bordercart-simplification-20261007/runtime-chain-current.json)。

## 配置启停与回滚

- 本地默认：不配置 `REDIS_URL`，或使用 `QUEUE_ENABLED=0`；API 进程内直接处理请求。
- 启用旧队列：配置 `REDIS_URL`、`QUEUE_ENABLED=1`，需要 Redis 服务和单独 worker；语义缓存/双队列优先级分别由 `SEMANTIC_CACHE_ENABLED=1`、`QUEUE_PRIORITY_ENABLED=1` 控制。
- 回滚本轮默认行为：在 `.env` 显式设置旧变量值并重启 API；代码回滚使用本分支提交历史，不删除 `data/`。
- `.env` 中的真实密钥未写入本记录，测试使用假值 `test-key`。

## 未完成项

- 后端全量回归已通过；真实 Redis 6.2+ 队列链路和 Langfuse 云端效果仍需相应外部环境才能验收。
- Redis/worker 兼容路径本轮只做默认关闭和文档整理，未删除历史模块。
- Compose 仍保留 Redis、worker 和 Qdrant 多容器编排作为高级部署入口；本轮只收缩其默认应用配置，不把该模式作为本地最小启动前置条件。
- 前端浏览器验收已确认 BorderCart AI 品牌、商品卡和 Personal Skill 页面可见；模型/Embedding 的生产效果指标未知。
- 当前工作树源码已在隔离 API `http://127.0.0.1:18000/health` 完成健康检查和真实链路；常驻 API `http://127.0.0.1:8000` 属于用户先前启动的旧源码进程，本轮未强制终止或覆盖它。前端 `http://127.0.0.1:5173/` 可访问，页面代理仍指向 8000。

## 关联版本

- 设计提交：`abff4a4 docs: 记录 BorderCart 项目简化设计`
- 实现提交：`ed4dcb8 refactor: simplify BorderCart local runtime`

后续收缩改动已提交于 `1f6ad4a refactor: make BorderCart core runtime opt-in`；验证兼容和稳定性修复提交于 `72382f8 fix: complete current runtime verification`。当前工作树额外保留用户未提交的 Windows 文件存储改动，未纳入本轮提交。

## GitHub 发布

- 已创建公开仓库：[1saachen/bordercart-ai-agent](https://github.com/1saachen/bordercart-ai-agent)。
- 上传分支：`main`；核心简化版提交为 `d067311cbf32d0cd5b66e196fb25d5c981d41f5a`，随后追加发布记录提交 `9bf7e39`；当前远端 `main` 指向后者。
- 发布前检查确认 `.env`、真实凭据和用户已有未提交文件均未上传；远端 README 可正常读取，`.env` 路径返回 404。
- 本地 `bordercart` remote 仅用于该仓库推送；原有 `origin` 远程未修改。
