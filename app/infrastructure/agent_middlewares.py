"""BorderCart 核心 Agent 中间件。

这里只保留上下文证据压缩和可选的单轮回复预算控制；外部追踪不属于核心运行时。
"""
from __future__ import annotations

from agentscope.middleware import ReplyBudgetControlMiddleware

from app.infrastructure.context_compaction import EvidenceCompactionMiddleware
from app.infrastructure.persistence.context_evidence import ContextEvidenceStore

_BUDGET_HINT = (
    "<system-reminder>本次会话已达到 Token 预算上限。请立即停止调用工具，"
    "基于当前已获得的信息给买家一个明确的收尾回复（如实说明信息可能不完整）。</system-reminder>"
)


def build_agent_middlewares(settings) -> list:
    """构造核心上下文中间件，不连接 OTLP、Langfuse 或其他外部追踪服务。"""
    if settings.context_strategy not in {"legacy", "layered"}:
        raise ValueError("CONTEXT_STRATEGY 仅支持 legacy/layered")
    if settings.context_pruning_timing not in {"after_use", "pressure"}:
        raise ValueError("CONTEXT_PRUNING_TIMING 必须是 after_use 或 pressure")

    if settings.context_strategy == "layered":
        from app.infrastructure.context_governance import LayeredContextMiddleware

        context_middleware = LayeredContextMiddleware(
            ContextEvidenceStore(settings.data_dir / "context_evidence.db"),
            product_tokens=settings.context_product_tokens,
            target_tokens=settings.context_target_tokens,
            timing=settings.context_pruning_timing,
            prompt_layout=settings.context_prompt_layout,
            state_mode=settings.context_state_mode,
            prune_low_ratio=settings.context_prune_low_ratio,
            compact_result_rules=settings.context_compact_result_rules,
        )
    else:
        context_middleware = EvidenceCompactionMiddleware(
            ContextEvidenceStore(settings.data_dir / "context_evidence.db")
        )

    middlewares = [context_middleware]
    if settings.reply_token_budget > 0:
        middlewares.append(
            ReplyBudgetControlMiddleware(
                token_budget=settings.reply_token_budget,
                hint_message=_BUDGET_HINT,
            )
        )
    return middlewares
