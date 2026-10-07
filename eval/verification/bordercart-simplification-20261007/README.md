# BorderCart AI 简化验证证据

源码分支：`codex/simplify-bordercart`

## 后端默认配置

命令：`.venv/Scripts/python.exe -m pytest tests/test_simplified_runtime.py -q`

原始结果：

```text
..                                                                       [100%]
2 passed, 1 warning in 0.10s
```

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

## 本地服务启动检查

前端已在 `http://127.0.0.1:5173/` 返回 HTTP 200，页面 HTML 已包含 `BorderCart AI · 跨境智选助手`。

API 复用了已占用本地 Qdrant 目录的现有进程（PID 54892），`GET http://127.0.0.1:8000/health` 返回 `status=ok`、`database=sqlite`、`trade_database=sqlite`、`redis=disabled`、`semantic_cache=false`、`queue=disabled`。尝试重复启动第二个 API 进程时按预期收到 Qdrant `Storage folder data\\qdrant is already accessed by another instance` 错误，因此没有强行终止原进程或删除锁文件。

## 全量后端回归

命令：`.venv/Scripts/python.exe -m pytest -q`

结果：`1276 passed, 1 skipped, 60 failed, 85 errors`。失败集中在既有 Windows 编码、Unix `/tmp` 临时目录和外部 Redis/模型前提；本轮只记录原始结果，不将其解释为简化功能通过。
