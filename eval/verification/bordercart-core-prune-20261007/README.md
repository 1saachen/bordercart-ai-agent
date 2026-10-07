# BorderCart 核心版裁剪验证

日期：2026-10-07（Asia/Shanghai）

本目录保存本次核心版裁剪的脱敏验证摘要。未保存 API key、`.env`、真实数据库或买家原文。

## 结果

- `python -m compileall -q app`：通过。
- 核心后端回归（运行时边界、Agent、KnowledgeBase、交易、Skill、表单）：`137 passed`。
- 前端 Vitest：`128 passed`，13 个测试文件。
- 前端生产构建：Vite 构建通过。

## 核心边界

保留 MainAgent -> SearchAgent/TradeAgent、多 Agent 工具调度、Embedding + Qdrant 商品检索、AgentScope KnowledgeBase、Personal Skill 买家隔离、交易确认、SQLite 和 AG-UI/SSE。

删除 Redis/队列/worker、语义缓存、Registry、公共 Skill、Harness、Web Search、HTTP reranker、外部 tracing、旧扩展评测和对应依赖入口。

## 限制

本记录未声称真实模型网关、真实 Qdrant 服务或生产业务效果已验收。真实链路需要使用独立数据目录和端口启动后单独记录。
