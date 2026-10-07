# -*- coding: utf-8 -*-
"""TradeEventBus

把 Agent 流式事件、工具调用事件统一汇聚到一个异步发布订阅总线，
Presentation 层按 shopping_session_id 订阅后推送给前端 WebSocket。

事件类型与参考实现语义一一对应：
    agent.dispatch      子 Agent 被调度
    tool.invoke         工具开始执行
    tool.result         工具执行完成
    token.delta         流式 token 增量
    plan.update         Task 计划变更
    context.compressed  上下文压缩发生
    model.fallback      主模型限流重试用尽，已回退到备用模型
    final.result        最终回复
    error               异常
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


TradeEventType = str

# 只观察当前执行任务及其子协程，避免同会话排队时混入另一轮的商品结果。
_run_observer: ContextVar[Callable[["TradeEvent"], None] | None] = ContextVar(
    "globex_trade_event_observer", default=None,
)


@contextmanager
def observe_run_events(observer: Callable[["TradeEvent"], None]):
    previous = _run_observer.get()
    def notify(event):
        if previous is not None:
            previous(event)
        observer(event)
    token = _run_observer.set(notify)
    try:
        yield
    finally:
        _run_observer.reset(token)

EVENT_TYPES = (
    "ui.surface",
    "agent.dispatch",
    "tool.invoke",
    "tool.result",
    "token.delta",
    "plan.update",
    "context.compressed",
    "model.fallback",
    "usage.summary",
    "confirmation.required",
    "confirmation.resolved",
    "skill.preload",
    "final.result",
    "error",
)


@dataclass(frozen=True)
class TradeEvent:
    shopping_session_id: str
    type: TradeEventType
    payload: Any
    occurred_at: str
    correlation: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "shopping_session_id": self.shopping_session_id,
            "type": self.type,
            "payload": self.payload,
            "occurred_at": self.occurred_at,
            "correlation": self.correlation,
        }

    @staticmethod
    def from_dict(raw: dict) -> "TradeEvent":
        return TradeEvent(
            shopping_session_id=raw["shopping_session_id"],
            type=raw["type"],
            payload=raw.get("payload"),
            occurred_at=raw.get("occurred_at", ""),
            correlation=raw.get("correlation", {}),
        )


@dataclass
class TradeEventBus:
    """进程内发布订阅：每个订阅者一个独立 Queue，互不阻塞。"""

    _subscribers: dict[str, list[asyncio.Queue]] = field(default_factory=dict)

    def subscribe(self, shopping_session_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(shopping_session_id, []).append(queue)
        return queue

    def unsubscribe(self, shopping_session_id: str, queue: asyncio.Queue) -> None:
        queues = self._subscribers.get(shopping_session_id, [])
        if queue in queues:
            queues.remove(queue)
        if not queues:
            self._subscribers.pop(shopping_session_id, None)

    def deliver_local(self, event: TradeEvent) -> None:
        """投递给当前进程订阅者。"""
        for queue in self._subscribers.get(event.shopping_session_id, []):
            queue.put_nowait(event)

    def publish(self, shopping_session_id: str, event_type: TradeEventType, payload: Any) -> None:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"未知事件类型：{event_type}")
        event = TradeEvent(
            shopping_session_id=shopping_session_id,
            type=event_type,
            payload=payload,
            occurred_at=datetime.now(timezone.utc).isoformat(),
            correlation={},
        )
        observer = _run_observer.get()
        if observer is not None:
            observer(event)
        self.deliver_local(event)
