from __future__ import annotations

import asyncio

import pytest

from app.application.usecases.catalog_search import CatalogSearchUseCase
from app.domain.catalog.money import Money
from app.domain.catalog.product import Product, ProductHighlight
from app.domain.catalog.product_search_spec import ProductSearchSpec
from app.domain.catalog.sku import Sku
from app.infrastructure.persistence.in_memory_repositories import InMemoryProductRepository


def _product(product_id: str, title: str, *, price: float = 10, stock: int = 5, canonical: str = "") -> Product:
    return Product(
        product_id=product_id,
        title=title,
        brand="BorderBrand",
        category="旅行装备",
        origin_country="CN",
        description=title,
        highlights=[ProductHighlight("用途", title)],
        ships_to=["CN"],
        canonical_product_id=canonical or product_id,
        skus=[Sku(f"{product_id}-S1", "标准", Money.from_major_units(price, "CNY"), stock)],
    )


class _Embedder:
    async def embed(self, text: str) -> list[float]:
        return [1.0, 0.0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


class _Vector:
    async def search(self, embedding, top_n):
        from app.domain.catalog.ports.retrieval_ports import VectorHit
        return [VectorHit("P0002", .90), VectorHit("P0001", .80), VectorHit("P0003", .70)][:top_n]


class _Reranker:
    configured = True

    async def rerank(self, query: str, documents: list[str]) -> list[float]:
        # 提高向量单路候选，证明精排发生在融合之后、Top-K 之前。
        return [.99 if "城市通勤包" in doc else .80 if "旅行背包" in doc else .10 for doc in documents]


class _FailingReranker:
    configured = True

    async def rerank(self, query: str, documents: list[str]) -> list[float]:
        raise RuntimeError("reranker unavailable")


@pytest.mark.asyncio
async def test_hybrid_fuses_keyword_and_vector_then_reranks_before_top_k():
    products = [_product("P0001", "轻便旅行背包"), _product("P0002", "城市通勤包"), _product("P0003", "折叠旅行包")]
    usecase = CatalogSearchUseCase(
        InMemoryProductRepository(products), embedder=_Embedder(), vector_index=_Vector(),
        hybrid_enabled=True, recall_candidates=8, reranker=_Reranker(),
    )

    result = await usecase.execute(ProductSearchSpec(normalized_query="轻便旅行背包", top_k=2))

    assert [item["product_id"] for item in result["hits"]] == ["P0002", "P0001"]
    assert result["recall_strategy"] == "hybrid_rerank"
    assert result["rerank_applied"] is True
    assert result["rerank_status"] == "applied"


@pytest.mark.asyncio
async def test_hybrid_filters_before_rerank_and_deduplicates_canonical_products():
    products = [
        _product("P0001", "旅行背包", price=10, canonical="CANONICAL-1"),
        _product("P0002", "旅行背包同款", price=100, canonical="CANONICAL-1"),
        _product("P0003", "轻便旅行包", price=20),
    ]
    usecase = CatalogSearchUseCase(
        InMemoryProductRepository(products), embedder=_Embedder(), vector_index=_Vector(),
        hybrid_enabled=True, recall_candidates=8, reranker=_Reranker(),
    )
    result = await usecase.execute(ProductSearchSpec(normalized_query="旅行背包", top_k=5, price_max_major=20))

    assert [item["product_id"] for item in result["hits"]] == ["P0001", "P0003"]
    assert any(item["product_id"] == "P0002" and item["reason"] == "over_price_cap" for item in result["filtered_out"])


@pytest.mark.asyncio
async def test_reranker_failure_returns_rrf_order_and_explicit_degraded_status():
    products = [_product("P0001", "轻便旅行背包"), _product("P0002", "城市通勤包")]
    usecase = CatalogSearchUseCase(
        InMemoryProductRepository(products), embedder=_Embedder(), vector_index=_Vector(),
        hybrid_enabled=True, recall_candidates=8, reranker=_FailingReranker(),
    )

    result = await usecase.execute(ProductSearchSpec(normalized_query="旅行背包", top_k=2))

    assert result["recall_strategy"] == "hybrid_rrf"
    assert result["rerank_applied"] is False
    assert result["rerank_status"] == "degraded"


@pytest.mark.asyncio
async def test_exact_id_lookup_does_not_call_reranker():
    class _ExplodingReranker:
        configured = True

        async def rerank(self, query, documents):
            raise AssertionError("exact ID lookup must bypass reranker")

    product = _product("P0001", "轻便旅行背包")
    usecase = CatalogSearchUseCase(InMemoryProductRepository([product]), reranker=_ExplodingReranker())
    result = await usecase.execute(ProductSearchSpec(product_id="P0001"))
    assert result["recall_strategy"] == "exact_id_lookup"
    assert result["rerank_applied"] is False


async def test_vector_failure_preserves_bm25_and_rerank_is_optional():
    class FailedVector:
        async def search(self, embedding, top_n):
            raise RuntimeError("synthetic network failure")
    products = [_product("P0001", "轻便旅行背包")]
    result = await CatalogSearchUseCase(
        InMemoryProductRepository(products), embedder=_Embedder(), vector_index=FailedVector(), hybrid_enabled=True,
    ).execute(ProductSearchSpec(normalized_query="旅行背包"))
    assert [p["product_id"] for p in result["hits"]] == ["P0001"]
    assert result["recall_strategy"] == "bm25"
    assert result["vector_available"] is False
    assert result["rerank_status"] == "not_configured"


async def test_two_routes_supply_complementary_candidates_and_canonical_duplicates_are_removed():
    from app.domain.catalog.ports.retrieval_ports import VectorHit
    class SemanticOnlyVector:
        async def search(self, embedding, top_n):
            return [VectorHit("P0002", .9), VectorHit("P0003", .8)]
    products = [_product("P0001", "WH-X55 旅行背包"), _product("P0002", "城市通勤包", canonical="same"),
                _product("P0003", "商务收纳包", canonical="same")]
    result = await CatalogSearchUseCase(
        InMemoryProductRepository(products), embedder=_Embedder(), vector_index=SemanticOnlyVector(),
        hybrid_enabled=True, capture_retrieval_stages=True,
    ).execute(ProductSearchSpec(normalized_query="WH-X55"))
    assert {p["product_id"] for p in result["hits"]} == {"P0001", "P0002"}
    assert result["retrieval_stages"]["lexical_candidates"] == ["P0001"]
    assert result["retrieval_stages"]["vector_candidates"] == ["P0002", "P0003"]


@pytest.mark.parametrize("change", ["stock", "ship_to", "category", "excluded_material", "required_material", "price"])
async def test_hard_constraints_are_enforced_before_candidates_reach_reranker(change):
    products = [_product("P0001", "旅行背包"), _product("P0002", "旅行背包违规候选")]
    spec = dict(normalized_query="旅行背包", ship_to="CN", category="旅行装备", price_max_major=20)
    if change == "stock":
        products[1].skus[0] = Sku("P0002-S1", "标准", Money.from_major_units(10, "CNY"), 0)
    elif change == "ship_to":
        products[1].ships_to = ["US"]
    elif change == "category":
        products[1].category = "办公学习"
    elif change == "excluded_material":
        products[1].material_tags = ["塑料"]
        spec["excluded_material_tags"] = ["塑料"]
    elif change == "required_material":
        products[0].material_tags = ["金属"]
        spec["required_material_tags"] = ["金属"]
    elif change == "price":
        products[1].skus[0] = Sku("P0002-S1", "标准", Money.from_major_units(100, "CNY"), 1)
    class AssertEligibleReranker:
        async def rerank(self, query, documents):
            assert len(documents) == 1 and "违规候选" not in documents[0]
            return [.8]
    result = await CatalogSearchUseCase(
        InMemoryProductRepository(products), embedder=_Embedder(), vector_index=_Vector(), hybrid_enabled=True,
        reranker=AssertEligibleReranker(),
    ).execute(ProductSearchSpec(**spec))
    assert result["rerank_status"] == "applied"
    assert [p["product_id"] for p in result["hits"]] == ["P0001"]


@pytest.mark.parametrize("scores", [[.1], [float("nan"), .2], [True, .2]])
async def test_invalid_rerank_scores_preserve_entire_rrf_order(scores):
    class InvalidReranker:
        async def rerank(self, query, documents):
            return scores
    repo = InMemoryProductRepository([_product("P0001", "旅行背包"), _product("P0002", "城市通勤包")])
    spec = ProductSearchSpec(normalized_query="旅行背包")
    plain = await CatalogSearchUseCase(repo, embedder=_Embedder(), vector_index=_Vector(), hybrid_enabled=True).execute(spec)
    ranked = await CatalogSearchUseCase(repo, embedder=_Embedder(), vector_index=_Vector(), hybrid_enabled=True,
                                        reranker=InvalidReranker()).execute(spec)
    assert ranked["hits"] == plain["hits"]
    assert ranked["rerank_status"] == "degraded"


async def test_rerank_cancel_is_not_converted_to_success_or_degradation():
    class CancelledReranker:
        async def rerank(self, query, documents):
            raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await CatalogSearchUseCase(InMemoryProductRepository([_product("P0001", "旅行背包")]),
                                   hybrid_enabled=True, reranker=CancelledReranker()).execute(ProductSearchSpec(normalized_query="旅行背包"))


async def test_candidate_window_bounds_rerank_request_and_ties_preserve_rrf_order():
    products = [_product(f"P{i:04d}", "旅行背包") for i in range(1, 31)]
    class EqualReranker:
        async def rerank(self, query, documents):
            assert len(documents) == 8
            return [.5] * len(documents)
    result = await CatalogSearchUseCase(InMemoryProductRepository(products), hybrid_enabled=True, recall_candidates=8,
                                        reranker=EqualReranker()).execute(ProductSearchSpec(normalized_query="旅行背包", top_k=2))
    assert [p["product_id"] for p in result["hits"]] == ["P0001", "P0002"]


async def test_product_tool_publishes_actual_rerank_status():
    import json
    from app.application.tools.product_search_tool import build_product_search_tool
    from app.infrastructure.eventbus import TradeEventBus, observe_run_events
    bus = TradeEventBus()
    events = []
    usecase = CatalogSearchUseCase(InMemoryProductRepository([_product("P0001", "旅行背包")]),
                                  hybrid_enabled=True, reranker=_Reranker())
    with observe_run_events(events.append):
        chunk = await build_product_search_tool(usecase, bus)(normalized_query="旅行背包")
    body = json.loads(chunk.content[0].text)
    published = next(e.payload for e in events if e.type == "tool.result")
    assert body["rerank_applied"] is published["rerank_applied"] is True
    assert body["rerank_status"] == published["rerank_status"] == "applied"
    assert [(p["product_id"], p["price_major"]) for p in body["hits"]] == [(p["product_id"], p["price_major"]) for p in published["hits"]]
