# BorderCart AI 简化验证证据

源码分支：`codex/simplify-bordercart`

## 后端默认配置

命令：`.venv/Scripts/python.exe -m pytest tests/test_simplified_runtime.py -q`

原始结果：

```text
....                                                                     [100%]
4 passed in 3.69s
```

本轮新增断言覆盖：默认不创建公共 Prompt/Capability Registry；Personal Skill 仍可独立装配；Harness、HTTP reranker 默认关闭；显式开关仍可读取。

核心后端定向回归：`.venv/Scripts/python.exe -m pytest tests/test_runtime_distribution.py tests/test_simplified_runtime.py tests/test_buyer_workspace.py tests/test_buyer_skills.py tests/test_selected_skill.py tests/test_skill_catalog.py tests/test_knowledge_fixture.py tests/test_harness_middleware.py -q`，`97 passed`。其中 `tests/test_runtime_distribution.py` 已将 Compose 文件读取改为显式 UTF-8，避免 Windows 默认 GBK 误报。

## 前端回归

命令：`npm test -- --run`（工作目录 `frontend`）

原始结果摘要：

```text
Test Files  13 passed (13)
Tests       128 passed (128)
```

命令：`npm run build`（工作目录 `frontend`）

原始结果摘要：

```text
vite v5.4.21 building for production...
607 modules transformed.
✓ built in 5.59s
```

## 定向后端回归限制

命令：`.venv/Scripts/python.exe -m pytest tests/test_simplified_runtime.py tests/test_reranker_client.py tests/test_retrieval.py -q`

结果：16 passed，10 errors。错误均发生在既有 `tests/test_retrieval.py` fixture 读取 `data/catalog-v1.jsonl` 时，Windows 默认编码为 GBK，触发 `UnicodeDecodeError`，没有进入本轮运行时或品牌改动逻辑。后续应单独统一该 fixture 的 UTF-8 读取并复测。

## 外部链路

本证据未声称模型、Embedding、Qdrant 或 KnowledgeBase 的生产效果已验收。历史启动证据见 [startup-20261003](../startup-20261003/)。

## 当前源码隔离实例

- `GET http://127.0.0.1:18000/health`：`status=ok`，SQLite 数据库与交易库，Redis/队列/语义缓存关闭；源码 SHA-256 为 `c3bf9fd0039f0cd877f42a4811c9903e873e921e3da843602cdb507c5c3f4578`。
- `POST /commerce/intents` 使用有效环境变量完成一次真实商品检索，返回 `P1003`、`P1049` 等结构化商品卡；未在证据中记录密钥或完整买家原文。
- `GET /commerce/skills?buyer_id=verify-buyer` 返回买家隔离 Skill 目录，当前为空，接口链路正常。

## 本地服务启动检查

前端已在 `http://127.0.0.1:5173/` 返回 HTTP 200，页面 HTML 已包含 `BorderCart AI · 跨境智选助手`。

API 复用了已占用本地 Qdrant 目录的现有进程（PID 54892），`GET http://127.0.0.1:8000/health` 返回 `status=ok`、`database=sqlite`、`trade_database=sqlite`、`redis=disabled`、`semantic_cache=false`、`queue=disabled`。尝试重复启动第二个 API 进程时按预期收到 Qdrant `Storage folder data\\qdrant is already accessed by another instance` 错误，因此没有强行终止原进程或删除锁文件。

## 全量后端回归

命令：`.venv/Scripts/python.exe -m pytest -q`

结果：`1276 passed, 1 skipped, 60 failed, 85 errors`。失败集中在既有 Windows 编码、Unix `/tmp` 临时目录和外部 Redis/模型前提；本轮只记录原始结果，不将其解释为简化功能通过。

Redis/队列定向复测：`15 passed, 43 skipped`。当前 Redis 为 5.0.14，真实队列所需的 `XAUTOCLAIM` 需要 Redis 6.2+；Windows 无 `AF_UNIX` 的 fixture 已改为本机随机 TCP 端口。

仍未通过的独立既有测试：AG-UI journal 2 项、eval feedback 2 项、Harness Windows 权限/symlink 5 项；未伪造通过。

## 依赖与配置检查

- `pyproject.toml` 和 `uv.lock` 均可由 Python `tomllib` 解析。
- 当前环境未安装 `uv`；尝试通过 pip 安装时代理不可用，未运行 `uv lock`。锁文件只做了与 optional `redis` extra 对应的最小同步，未宣称经过 uv 重新解析。
- 本轮未修改用户已有的 `app/infrastructure/persistence/json_file_stores.py`、`tests/test_windows_file_store.py` 和 `eval/verification/startup-20261003/`。
