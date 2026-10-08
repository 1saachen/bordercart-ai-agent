"""真实本地 Qdrant 与 TCP/HTTP 联调；评分服务是确定性替身，不能证明模型效果。"""
from __future__ import annotations

import json
import threading
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.application.tools.product_search_tool import build_product_search_tool
from app.application.usecases.catalog_search import CatalogSearchUseCase
from app.infrastructure.embedding.openai_embedding_client import OpenAIEmbeddingClient
from app.infrastructure.eventbus import TradeEventBus, observe_run_events
from app.infrastructure.persistence.in_memory_repositories import InMemoryProductRepository
from app.infrastructure.retrieval.reranker import HTTPReranker
from app.infrastructure.settings import load_settings
from app.infrastructure.vector.index_bootstrap import bootstrap_product_index
from app.infrastructure.vector.qdrant_product_index import QdrantProductIndex
from tests.test_product_hybrid_rerank import _product


@pytest.mark.parametrize("use_reranker", [False, True])
async def test_real_local_qdrant_and_http_rerank_reach_product_tool(monkeypatch, tmp_path, use_reranker):
    paths = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            paths.append(self.path)
            if self.path == "/v1/embeddings":
                result = {"data": [{"index": i, "embedding": [1., .2 if "城市" in text else 0.]}
                                   for i, text in enumerate(body["input"])]}
            elif self.path == "/v1/rerank":
                assert body["top_n"] == len(body["documents"])
                result = {"results": [{"index": i, "relevance_score": .99 if "城市" in doc else .2}
                                      for i, doc in reversed(list(enumerate(body["documents"])))]}
            else:
                self.send_error(404)
                return
            response = json.dumps(result).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    index = None
    try:
        # 隔离本机系统代理，确保回环 HTTP 替身不被转发到代理网关。
        monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
        monkeypatch.setenv("LLM_API_KEY", "synthetic-test-key")
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        endpoint = f"http://127.0.0.1:{server.server_port}/v1"
        settings = replace(load_settings(), qdrant_url="", embedding_base_url=endpoint,
                           embedding_api_key="synthetic-test-key", embedding_model="synthetic-embedding", embedding_dim=2)
        repo = InMemoryProductRepository([_product("P0001", "旅行背包"), _product("P0002", "城市通勤包")])
        embedder = OpenAIEmbeddingClient(settings)
        index = QdrantProductIndex(settings)
        assert await bootstrap_product_index(repo, embedder, index)
        assert await index.products_needing_embeddings(await repo.list_all()) == []
        usecase = CatalogSearchUseCase(repo, embedder=embedder, vector_index=index, hybrid_enabled=True,
                                      reranker=HTTPReranker(endpoint, "synthetic-reranker") if use_reranker else None)
        events = []
        with observe_run_events(events.append):
            result = await build_product_search_tool(usecase, TradeEventBus())(normalized_query="旅行背包", top_k=2)
        content = json.loads(result.content[0].text)
        assert [p["product_id"] for p in content["hits"]] == (["P0002", "P0001"] if use_reranker else ["P0001", "P0002"])
        assert content["recall_strategy"] == ("hybrid_rerank" if use_reranker else "hybrid_rrf")
        assert content["rerank_status"] == ("applied" if use_reranker else "not_configured")
        assert content["vector_available"] is True
        assert "/v1/embeddings" in paths
        assert ("/v1/rerank" in paths) is use_reranker
        assert next(e.payload for e in events if e.type == "tool.result")["rerank_applied"] is use_reranker
    finally:
        if index is not None:
            await index.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_new_retrieval_config_preserves_secret_redaction(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LLM_API_KEY", "synthetic-chat-key")
    monkeypatch.setenv("RERANKER_API_KEY", "synthetic-rerank-key")
    monkeypatch.setenv("HYBRID_RECALL_ENABLED", "1")
    monkeypatch.setenv("RERANKER_BASE_URL", "http://127.0.0.1:18081/v1")
    monkeypatch.setenv("RERANKER_MODEL", "test-model")
    settings = load_settings()
    assert settings.hybrid_recall_enabled is True
    assert settings.reranker_model == "test-model"
    assert "synthetic-rerank-key" not in repr(settings)
