# BorderCart AI 项目简化设计

## 1. 目标

将项目收缩为适合简历展示和本地运行的跨境电商 Agent，同时保留最能体现 AI Agent / LLM 工程能力的主链路：多 Agent 协作、商品 RAG、品类 KnowledgeBase RAG 和 Personal Skill。

前端产品显示名统一为 **BorderCart AI**，中文副标题使用“跨境智选助手”。内部 Python 包名、API 路径、数据库表名和 Git 远程地址暂不修改，避免产生不必要的兼容性风险。

## 2. 保留范围

### Agent 协作

保留 `MainAgent`、`SearchAgent`、`TradeAgent` 三个角色。`MainAgent` 负责意图理解和任务编排，通过现有任务调度边界调用搜索和交易 Agent；不改变 AgentScope 的消息、工具调用和流式事件契约。

### 检索与知识

保留两条检索能力：

1. 商品 RAG：Embedding、Qdrant 商品索引、结构化过滤和商品候选召回。
2. KnowledgeBase RAG：品类 Markdown 文档、AgentScope `KnowledgeBase` 和 Qdrant 检索，为选购建议、商品比较和注意事项提供证据。

两条路径继续由 `SearchAgent` 或其工具边界使用；不改动向量数据格式和本地 `data/qdrant` 目录约定。

### Personal Skill

保留个人 Skill 的 CRUD、SQLite 持久化、买家隔离、版本/hash、输入框 `/` 选择和按需加载到 Agent 上下文。Skill 只影响现有 Agent 的指导语境，不获得新的工具权限。暂不实现公共 Skill 的审核、发布和版本流量管理。

### 运行方式

保留 FastAPI + Uvicorn、React/Vite、SQLite、本地 Qdrant、Embedding 服务和核心 SSE/AG-UI 流式接口。默认本地启动应只需 API、前端和模型/Embedding 环境变量，不要求预先启动 Redis。

## 3. 收缩范围

优先从默认启动链路和组合根中移除非核心依赖，避免一次性删除仍被测试或历史接口引用的代码：

- Redis cache、Redis Streams、独立 worker 和跨进程事件背板；
- 复杂 Prompt Registry、Capability Registry 和公共 Skill 发布流程；
- semantic cache、独立 reranker、复杂共享限流/熔断接线；
- Drift Detector、Loop Detector 和非必要的上下文治理接线；
- 非核心 Langfuse/OpenTelemetry 生产接线；
- Web 搜索和其他不属于本地商品/知识库闭环的外部能力。

如果某模块仍被现有核心路径或测试直接依赖，先采用默认关闭或轻量适配，不进行无证据的物理删除。README 和启动配置以“单进程本地模式”为主，明确可选能力和回滚方式。

## 4. 前端调整

把用户可见品牌从 Globex 调整为 BorderCart AI，并保留中文场景说明“跨境智选助手”。重点修改页面标题、meta 描述、导航品牌、欢迎文案和与 Agent 对话相关的提示文案；不修改接口字段和组件内部标识。

前端信息架构收敛为四个核心入口：对话/任务编排、商品检索与比较、KnowledgeBase/品类知识、Personal Skill。已有订单确认、商品详情和恢复能力作为对话流程中的必要子视图保留，不另起复杂导航体系。

## 5. 数据流

```text
用户请求
  -> MainAgent
      -> SearchAgent -> 商品 RAG / KnowledgeBase RAG
      -> TradeAgent  -> 购物车 / 订单确认
      -> Personal Skill 上下文（按需注入）
  -> SSE / AG-UI 流式响应
```

默认链路全部在 API 进程内执行。SQLite 保存会话、交易和 Personal Skill；Qdrant 保存商品与品类知识向量；模型和 Embedding 通过环境变量配置。Redis 未配置时健康检查应显示 disabled，而不是阻断核心链路。

## 6. 错误处理与兼容性

- Qdrant、Embedding 或模型不可用时，健康检查和错误消息应明确指出对应依赖，不伪造检索结果。
- KnowledgeBase 没有命中时返回“暂无相关知识证据”，由 Agent 决定是否继续用商品检索，不让空证据变成事实陈述。
- Personal Skill 加载失败只影响 Skill 注入，不应阻断普通商品搜索。
- 保留现有确认机制，交易写操作继续要求明确确认。
- 不改动已有环境变量名称；移除/停用的 Redis 配置保留兼容读取并标注为可选。

## 7. 验证标准

计划分阶段验证：

1. 静态检查：核心导入、类型检查、前端构建。
2. 后端回归：现有测试集，重点覆盖 Agent 调度、商品检索、KnowledgeBase、Skill 和交易确认。
3. 启动验证：单进程 API、前端、`/health`，确认无 Redis 时可启动。
4. 真实外部链路：使用当前环境变量验证模型、Embedding、商品向量检索和 KnowledgeBase 检索；将结果和限制记录到当天改动记录及 `eval/verification/`。
5. 前端验收：确认 BorderCart AI 文案、对话流式展示、商品候选、KnowledgeBase 证据和 Personal Skill `/` 选择均可用。

测试通过只证明代码路径成立，不替代外部模型服务可用性或生产效果结论。

## 8. 非目标

- 本轮不把 AgentScope 全量迁移到 LangChain。
- 本轮不重写 Qdrant、Embedding 或 KnowledgeBase 实现。
- 本轮不引入新的云数据库、消息队列或部署平台。
- 本轮不改变交易业务规则和买家数据隔离策略。
