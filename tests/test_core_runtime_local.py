"""BorderCart 核心版运行时边界回归。"""

from __future__ import annotations

import inspect


def test_settings_and_container_expose_only_local_core_runtime():
    from app.composition import Container
    from app.infrastructure.settings import Settings

    forbidden = {
        "redis_url",
        "semantic_cache_enabled",
        "semantic_cache_threshold",
        "queue_enabled",
        "queue_wait_seconds",
        "worker_concurrency",
        "queue_priority_enabled",
        "queue_large_request_turns",
        "prompt_registry_enabled",
        "prompt_pin_version",
        "public_skills_enabled",
        "harness_enabled",
        "loop_repeat_threshold",
        "drift_detect_enabled",
        "reranker_mode",
        "reranker_protocol",
        "tavily_api_key",
        "otlp_endpoint",
        "otlp_traces_endpoint",
        "otlp_headers",
        "otlp_traces_headers",
        "langfuse_base_url",
        "langfuse_public_key",
        "langfuse_secret_key",
        "otel_service_name",
        "otlp_timeout_seconds",
    }
    assert not forbidden.intersection(Settings.__dataclass_fields__)
    assert not forbidden.intersection(inspect.signature(Container).parameters)


def test_health_and_intent_routes_are_single_process_core_only():
    from app.presentation.server import build_app

    paths = {route.path for route in build_app().routes}
    assert "/commerce/intents" in paths
    assert "/health" in paths
    assert "/commerce/intents/async" not in paths
    assert not any(path.startswith("/commerce/tasks/") for path in paths)
