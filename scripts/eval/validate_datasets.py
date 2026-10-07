# -*- coding: utf-8 -*-
"""商品与品类 KnowledgeBase 数据的发布前校验。"""
from __future__ import annotations

import json
from pathlib import Path

from app.infrastructure.persistence.in_memory_repositories import InMemoryProductRepository
from scripts.eval.data_quality import validate_catalog_distribution, validate_catalog_products, validate_catalog_raw_records
from scripts.eval.knowledge_quality import count_knowledge_chunks, load_knowledge_manifest, validate_knowledge_content, validate_knowledge_manifest

_KNOWLEDGE_DIR = Path("knowledge")
_CATALOG_FIXTURE = Path("data") / "catalog-v2.jsonl"


def _load(path: Path) -> list[tuple[int, dict]]:
    return [(line, json.loads(raw)) for line, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1) if raw.strip()]


async def validate_knowledge_fixture() -> list[str]:
    try:
        manifest = load_knowledge_manifest(_KNOWLEDGE_DIR)
    except ValueError as err:
        return [str(err)]
    problems = validate_knowledge_manifest(_KNOWLEDGE_DIR, manifest)
    problems.extend(validate_knowledge_content(_KNOWLEDGE_DIR))
    count = await count_knowledge_chunks(_KNOWLEDGE_DIR)
    if not 150 <= count <= 250:
        problems.append(f"知识 chunk 数 {count} 不在 [150, 250] 范围内")
    return problems


async def validate_catalog_fixture() -> list[str]:
    products = await InMemoryProductRepository().list_all()
    problems = validate_catalog_products(products) + validate_catalog_distribution(products)
    try:
        records = _load(_CATALOG_FIXTURE)
        problems.extend(validate_catalog_raw_records([record for _, record in records]))
    except (OSError, json.JSONDecodeError) as err:
        problems.append(f"无法读取版本化商品数据：{err}")
    return problems
