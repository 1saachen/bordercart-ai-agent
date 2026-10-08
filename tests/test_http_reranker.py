"""在 HTTP 网络边界验证精排协议，不替换响应解析与业务排序。"""
import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from app.infrastructure.retrieval import reranker as mod


def install_transport(monkeypatch, handler):
    client = httpx.AsyncClient
    def factory(**kwargs):
        return client(transport=httpx.MockTransport(handler), **kwargs)
    monkeypatch.setattr(mod.httpx, "AsyncClient", factory)


@pytest.mark.parametrize("field", ["results", "data"])
async def test_maps_relevance_scores_by_index_not_response_position(monkeypatch, field):
    def handler(request):
        assert request.url.path == "/v1/rerank"
        assert request.headers["Authorization"] == "Bearer synthetic-test-key"
        assert json.loads(request.content) == {"query": "backpack", "model": "test-rerank", "documents": ["a", "b"], "top_n": 2}
        return httpx.Response(200, json={field: [{"index": 1, "relevance_score": .9}, {"index": 0, "relevance_score": .1}]})
    install_transport(monkeypatch, handler)
    result = await mod.HTTPReranker("https://example.invalid/v1", "test-rerank", "synthetic-test-key").rerank("backpack", ["a", "b"])
    assert result == [.1, .9]


@pytest.mark.parametrize("body", [
    {"error": {"message": "private provider details"}},
    {"error": "failure", "results": [{"index": 0, "relevance_score": .1}, {"index": 1, "relevance_score": .9}]},
    {"results": [{"index": 0, "relevance_score": .1}]},
    {"results": [{"index": 0, "relevance_score": .1}, {"index": 0, "relevance_score": .9}]},
    {"results": [{"index": -1, "relevance_score": .1}, {"index": 1, "relevance_score": .9}]},
    {"results": [{"index": 0, "relevance_score": .1}, {"index": 2, "relevance_score": .9}]},
    {"results": [{"index": False, "relevance_score": .1}, {"index": 1, "relevance_score": .9}]},
    {"results": [{"index": 0, "relevance_score": True}, {"index": 1, "relevance_score": .9}]},
    {"results": [{"index": 0, "relevance_score": "0.5"}, {"index": 1, "relevance_score": .9}]},
    {"results": [{"index": 0}, {"index": 1, "relevance_score": .9}]},
])
async def test_invalid_or_business_error_response_is_rejected_without_body_leak(monkeypatch, body):
    install_transport(monkeypatch, lambda request: httpx.Response(200, json=body))
    with pytest.raises(mod.RerankerError) as failure:
        await mod.HTTPReranker("https://example.invalid/rerank", "test").rerank("query", ["a", "b"])
    assert "private provider details" not in str(failure.value)


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -float("inf")])
def test_non_finite_scores_are_rejected(score):
    with pytest.raises(mod.RerankerError):
        mod.HTTPReranker._parse_scores({"results": [{"index": 0, "relevance_score": score}]}, 1)


@pytest.mark.parametrize("failure_type", [httpx.ReadTimeout, httpx.ConnectError])
async def test_network_failure_uses_safe_error_message(monkeypatch, failure_type):
    def handler(request):
        raise failure_type("private-provider-message synthetic-test-key", request=request)
    install_transport(monkeypatch, handler)
    with pytest.raises(mod.RerankerError) as failure:
        await mod.HTTPReranker("https://example.invalid/v1", "test", "synthetic-test-key").rerank("query", ["a"])
    assert "synthetic-test-key" not in str(failure.value)
    assert "private-provider-message" not in str(failure.value)


async def test_http_status_and_invalid_json_are_not_success(monkeypatch):
    for response in [httpx.Response(503, text="private-error"), httpx.Response(200, content=b"not-json")]:
        install_transport(monkeypatch, lambda request: response)
        with pytest.raises(mod.RerankerError):
            await mod.HTTPReranker("https://example.invalid/rerank", "test").rerank("query", ["a"])
        monkeypatch.undo()


async def test_cancelled_request_propagates(monkeypatch):
    def handler(request):
        raise asyncio.CancelledError()
    install_transport(monkeypatch, handler)
    with pytest.raises(asyncio.CancelledError):
        await mod.HTTPReranker("https://example.invalid/rerank", "test").rerank("query", ["a"])


async def test_empty_documents_do_not_make_request(monkeypatch):
    def handler(request):
        pytest.fail("no HTTP call for empty candidates")
    install_transport(monkeypatch, handler)
    assert await mod.HTTPReranker("https://example.invalid/rerank", "test").rerank("query", []) == []


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), True, 100])
def test_invalid_timeout_is_rejected(timeout):
    with pytest.raises(ValueError):
        mod.HTTPReranker("https://example.invalid/rerank", "test", timeout_seconds=timeout)


def test_unconfigured_reranker_does_not_reuse_chat_secret():
    settings = SimpleNamespace(reranker_base_url="", reranker_model="", reranker_api_key="", reranker_timeout_seconds=8, llm_api_key="chat-only")
    assert mod.build_reranker(settings) is None


async def test_timeout_bounds_total_request_even_when_transport_stalls(monkeypatch):
    async def handler(request):
        await asyncio.sleep(.2)
        return httpx.Response(200, json={"results": [{"index": 0, "relevance_score": 1}]})
    install_transport(monkeypatch, handler)
    with pytest.raises(mod.RerankerError, match="TimeoutError"):
        await mod.HTTPReranker("https://example.invalid/rerank", "test", timeout_seconds=.01).rerank("query", ["a"])
