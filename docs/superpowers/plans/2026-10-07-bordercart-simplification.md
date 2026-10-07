# BorderCart AI 项目简化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不损伤多 Agent、商品 RAG、KnowledgeBase RAG 和 Personal Skill 的前提下，将项目默认运行链路收缩为无需 Redis/worker 的单进程本地模式，并将前端品牌调整为 BorderCart AI。

**Architecture:** 保留现有 AgentScope 组合根和 FastAPI/React 边界，通过默认配置关闭 Redis 队列、跨进程事件背板和非核心治理；商品检索与 KnowledgeBase 检索继续由 SearchAgent 使用，Personal Skill 继续从 SQLite 注入 Agent 上下文。前端只做用户可见品牌和核心入口文案收敛，不改 API 契约。

**Tech Stack:** Python 3、FastAPI、Uvicorn、AgentScope、SQLite、Qdrant、本地 Embedding、React、Vite、SSE/AG-UI、pytest、Vitest。

---

## 文件边界

- 修改 `app/infrastructure/settings.py`：确认本地单进程模式的默认配置和 Redis 可选语义。
- 修改 `app/composition.py`：让默认组合根不创建 Redis 队列/背板和非核心治理对象，同时保持核心工厂接口稳定。
- 修改 `app/presentation/server.py`：同步健康检查、启动说明和可选依赖状态。
- 视导入结果修改 `app/application/agents/orchestrator.py`、`app/application/agents/main_agent.py`、`app/infrastructure/harness_middleware.py`：只在默认路径确实需要时移除复杂治理接线，保留核心执行和确认机制。
- 修改 `frontend/index.html`、`frontend/src/App.tsx`、`frontend/src/components/ContextWorkspace.tsx` 及命中文案文件：统一 BorderCart AI / 跨境智选助手显示名。
- 修改 `README.md`：以单进程本地启动为主，说明商品 RAG、KnowledgeBase、Personal Skill，标注 Redis/worker 为可选历史能力。
- 创建 `tests/test_simplified_runtime.py` 或复用现有测试目录：覆盖无 Redis 配置的组合根和健康状态。
- 修改或创建 `frontend/tests/brand.test.tsx`：覆盖用户可见品牌文案。
- 创建 `docs/改动记录/2026-10-07/README.md` 和功能记录：记录需求、变更、验证证据、配置启停/回滚说明和未完成项。
- 将真实启动日志或截图放入 `eval/verification/`，只引用原始证据，不写入凭据。

### Task 1: 固化默认单进程运行模式

**Files:**
- Modify: `app/infrastructure/settings.py`
- Modify: `app/composition.py`
- Modify: `app/presentation/server.py`
- Test: `tests/test_simplified_runtime.py`

- [x] **Step 1: 写失败测试，锁定 Redis 未配置时的行为**

```python
def test_local_runtime_does_not_require_redis(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("QUEUE_ENABLED", "0")
    from app.composition import build_container

    container = build_container()
    assert container.backplane is None
    assert container.settings.queue_enabled is False
```

- [x] **Step 2: 运行测试确认当前行为不满足或记录现有差异**

运行：`pytest tests/test_simplified_runtime.py::test_local_runtime_does_not_require_redis -q`

预期：在当前实现不满足时失败；若组合根已满足，则记录为基线通过并继续补齐健康接口断言。

- [x] **Step 3: 实现最小配置和组合根改动**

保持 `REDIS_URL`、`QUEUE_ENABLED` 兼容读取；当队列未显式开启或 Redis URL 为空时，创建进程内队列/事件实现或现有同步降级，不实例化 Redis Stream、Redis backplane、Redis cache 的强依赖。不要删除核心 Agent 工厂、Qdrant、KnowledgeBase 或 Skill 服务。

- [x] **Step 4: 补充健康接口测试**

```python
def test_health_marks_redis_optional(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("QUEUE_ENABLED", "0")
    from app.presentation.server import create_app

    app = create_app()
    response = app.test_client().get("/health")
    assert response.json["redis"] == "disabled"
    assert response.json["ready"] is True
```

若项目测试客户端不是上述接口，按现有 FastAPI 测试 fixture 使用 `httpx.AsyncClient`，断言保持相同语义。

- [x] **Step 5: 运行后端定向测试并提交**

运行：`pytest tests/test_simplified_runtime.py -q`

预期：全部通过。提交：`git add app/infrastructure/settings.py app/composition.py app/presentation/server.py tests/test_simplified_runtime.py && git commit -m "refactor: simplify local runtime dependencies"`

### Task 2: 收缩非核心治理的默认接线

**Files:**
- Modify: `app/composition.py`
- Modify: `app/application/agents/orchestrator.py`
- Modify: `app/application/agents/main_agent.py`
- Modify: `app/infrastructure/harness_middleware.py`
- Test: 现有 Agent 调度和流式测试，必要时新增 `tests/test_core_agent_wiring.py`

- [x] **Step 1: 盘点真实调用方和测试依赖**

运行：`rg -n "LoopDetector|DriftDetector|PromptRegistry|CapabilityRegistry|semantic_cache|rerank|harness" app tests`

把仍被商品 RAG、KnowledgeBase、Personal Skill、确认流程直接需要的对象列为保留项；只对默认组合根做可选注入，不物理删除仍被测试引用的模块。

- [x] **Step 2: 写核心接线回归测试**

测试必须验证：`MainAgent` 可以构造搜索和交易工厂；`SearchAgent` 仍收到 `KnowledgeBase`；Personal Skill 上下文仍可选加载；交易确认仍存在。测试使用 fake model/tool，不调用真实外部服务。

- [x] **Step 3: 实现默认关闭非核心治理**

将复杂缓存、Prompt/Capability 注册、Drift/Loop 检测、独立 reranker 和观测接线改为显式开关；默认关闭时传入 `None` 或现有轻量实现。保留 AgentScope 的 `Msg`、工具调用、流式事件和确认 API。

- [x] **Step 4: 运行 Agent 核心回归**

运行：`pytest tests -q -k "agent or search or skill or knowledge or confirmation"`

预期：核心路径通过；若历史测试依赖高级设施，单独标注为可选兼容测试，不改变核心默认链路。

- [x] **Step 5: 提交治理接线变更**

提交：`git add app tests && git commit -m "refactor: keep core agent path lightweight"`

### Task 3: 统一 BorderCart AI 前端品牌

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/ContextWorkspace.tsx`
- Test: `frontend/tests/brand.test.tsx`

- [x] **Step 1: 写品牌回归测试**

测试渲染首页后断言出现 `BorderCart AI` 和 `跨境智选助手`，并断言用户可见主标题不再出现 `Globex`；API 字段和组件内部测试标识不纳入替换范围。

- [x] **Step 2: 运行 Vitest 确认测试先失败**

运行：`npm --prefix frontend test -- --run frontend/tests/brand.test.tsx`

预期：当前品牌文案断言失败。

- [x] **Step 3: 修改页面品牌文案**

更新 `<title>`、meta description、品牌标识、首页欢迎语、对话提示和 ContextWorkspace 提示为 BorderCart AI / 跨境智选助手。保留订单、商品、Skill 和恢复功能文案，不新增复杂导航。

- [x] **Step 4: 运行前端测试和构建**

运行：`npm --prefix frontend test -- --run`

运行：`npm --prefix frontend run build`

预期：测试和构建通过。

- [x] **Step 5: 提交品牌改动**

提交：`git add frontend && git commit -m "feat: rename storefront to BorderCart AI"`

### Task 4: 整理 README 和运行入口

**Files:**
- Modify: `README.md`
- Modify: `docker/docker-compose.yaml`（仅当默认文档仍强制 worker/Redis 时）
- Modify: `package` 或启动脚本（仅当实际入口需要）

- [x] **Step 1: 以当前真实入口为基准更新文档**

明确 API、前端、SQLite、本地 Qdrant、模型/Embedding 环境变量的启动方式；说明 Redis/worker 是可选历史接口，不把它们写成默认前置依赖。

- [x] **Step 2: 添加简化后的架构说明**

用一段短流程说明 `MainAgent -> SearchAgent/TradeAgent`，并标注 SearchAgent 同时使用商品 RAG 与 KnowledgeBase RAG，Personal Skill 按需注入。

- [x] **Step 3: 添加配置启停和回滚说明**

说明删除 `REDIS_URL` 或设置 `QUEUE_ENABLED=0` 会回到单进程模式；恢复旧队列模式只需重新配置原变量并启动 worker。不得写入真实 API key 或数据库内容。

- [x] **Step 4: 运行文档引用检查**

运行：`rg -n "Globex|Redis|worker|BorderCart|KnowledgeBase|Personal Skill" README.md frontend/index.html frontend/src app/presentation/server.py`

确认用户可见品牌已统一、Redis 仅标注可选、核心能力说明与代码一致。

### Task 5: 真实启动、RAG/Skill 验证和改动记录

**Files:**
- Create: `docs/改动记录/2026-10-07/README.md`
- Create: `docs/改动记录/2026-10-07/BorderCart项目简化.md`
- Create/modify: `eval/verification/` 原始日志或截图

- [x] **Step 1: 运行全量后端测试和前端验证**

运行：`pytest -q`

运行：`npm --prefix frontend test -- --run && npm --prefix frontend run build`

记录真实命令、退出码、失败样本和未验证项。

- [x] **Step 2: 启动 API 和前端单进程模式**

使用现有 `.env`，启动 API 与 Vite；访问 `http://127.0.0.1:8000/health` 和 `http://127.0.0.1:5173/`。确认 Redis 未配置时 API 仍 ready，Qdrant 使用本地 `data/qdrant`。

- [x] **Step 3: 验证核心业务链路**

验证商品向量召回、KnowledgeBase 品类知识召回、Personal Skill 创建/选择/注入、MainAgent 到 SearchAgent/TradeAgent 的协作和交易确认。真实外部模型/Embedding 失败时记录原始错误，不把代码测试结果写成外部服务成功。

- [x] **Step 4: 编写当天改动记录**

记录需求、设计与实现、回归测试、真实外部链路、效果验收、配置启停、回滚、未完成项、关联 commit；链接 `eval/verification/` 下原始证据。

- [x] **Step 5: 最终检查并提交**

运行：`git diff --check`、`git status --short --branch`、`git log --oneline -5`。

确认不覆盖用户已有的 `app/infrastructure/persistence/json_file_stores.py`、`tests/test_windows_file_store.py` 和 `eval/verification/startup-20261003/` 改动，再提交记录：`git add docs/改动记录/2026-10-07 && git commit -m "docs: record BorderCart simplification verification"`。

---

## 计划自审

- 设计中的四项核心能力均有任务覆盖：三 Agent（Task 1/2）、商品 RAG 与 KnowledgeBase（Task 2/5）、Personal Skill（Task 2/5）、前端品牌（Task 3）。
- Redis/worker/复杂治理只做默认收缩和兼容说明，没有要求无证据删除历史模块。
- 验证覆盖静态、后端、前端、启动和真实外部链路，并按项目规则记录证据。
- 现有未提交用户改动明确列入保护范围。
