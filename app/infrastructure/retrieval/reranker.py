# -*- coding: utf-8 -*-
"""商品候选 HTTP Reranker 适配器。"""
from __future__ import annotations

import asyncio
import math
from typing import Any

import httpx


class RerankerError(RuntimeError):
    """Reranker 响应不可用或服务请求失败。"""


class HTTPReranker:
    configured = True

    def __init__(self, base_url: str, model: str, api_key: str = "", timeout_seconds: float = 8.0) -> None:
        if not base_url.strip() or not model.strip():
            raise ValueError("Reranker 需要同时配置 RERANKER_BASE_URL 和 RERANKER_MODEL")
        if (isinstance(timeout_seconds, bool) or not math.isfinite(timeout_seconds)
                or not 0 < timeout_seconds <= 30):
            raise ValueError("精排超时须为 (0, 30] 秒内的有限数值")
        self._url = base_url.strip().rstrip("/")
        if not self._url.endswith("/rerank"):
            self._url += "/rerank"
        self._model = model
        self._api_key = api_key
        self._timeout = timeout_seconds

    async def rerank(self, query: str, documents: list[str]) -> list[float]:
        if not documents:
            return []
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                # HTTPX 超时针对网络阶段；额外约束请求总耗时，避免慢响应长期占用检索。
                response = await asyncio.wait_for(
                    client.post(
                        self._url,
                        headers=headers,
                        json={"model": self._model, "query": query, "documents": documents, "top_n": len(documents)},
                    ),
                    timeout=self._timeout,
                )
                response.raise_for_status()
                body = response.json()
        except asyncio.CancelledError:
            raise
        except Exception as err:
            raise RerankerError(f"reranker 请求失败：{type(err).__name__}") from err
        return self._parse_scores(body, len(documents))

    @staticmethod
    def _parse_scores(body: Any, size: int) -> list[float]:
        if isinstance(body, dict) and body.get("error"):
            raise RerankerError("reranker 服务返回业务错误")
        rows = body.get("results", body.get("data")) if isinstance(body, dict) else None
        if not isinstance(rows, list) or len(rows) != size:
            raise RerankerError("reranker 响应必须返回完整候选结果")
        scores: list[float | None] = [None] * size
        for row in rows:
            if not isinstance(row, dict) or type(row.get("index")) is not int:
                raise RerankerError("reranker 响应缺少合法 index")
            index = row["index"]
            score = row.get("relevance_score", row.get("score"))
            if index < 0 or index >= size or scores[index] is not None:
                raise RerankerError("reranker 响应 index 重复或越界")
            if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(float(score)):
                raise RerankerError("reranker 响应包含非法分数")
            scores[index] = float(score)
        if any(score is None for score in scores):
            raise RerankerError("reranker 响应缺少候选分数")
        return [float(score) for score in scores]


def build_reranker(settings):
    """未配置服务时返回 None，商品检索会保留 RRF/BM25 排名。"""
    if not settings.reranker_base_url or not settings.reranker_model:
        return None
    return HTTPReranker(settings.reranker_base_url, settings.reranker_model, settings.reranker_api_key, settings.reranker_timeout_seconds)
