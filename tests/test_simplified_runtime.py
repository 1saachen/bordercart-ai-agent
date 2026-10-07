"""BorderCart 核心版的运行时边界。"""

from app.infrastructure.settings import load_settings


def _core_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("QDRANT_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)


def test_core_settings_keep_local_qdrant_and_no_extension_switches(monkeypatch, tmp_path):
    _core_environment(monkeypatch, tmp_path)
    settings = load_settings()
    assert settings.qdrant_url == ""
    assert settings.data_dir == tmp_path
    for name in ("redis_url", "queue_enabled", "semantic_cache_enabled",
                 "prompt_registry_enabled", "public_skills_enabled",
                 "harness_enabled", "reranker_mode", "tavily_api_key"):
        assert not hasattr(settings, name), f"扩展配置仍暴露在 Settings: {name}"


async def test_core_container_does_not_expose_extension_services(monkeypatch, tmp_path):
    _core_environment(monkeypatch, tmp_path)
    from app.composition import build_container
    container = await build_container()
    try:
        for name in ("cache", "semantic_cache", "task_queue", "backplane", "prompt_registry"):
            assert not hasattr(container, name), f"核心容器仍暴露扩展服务: {name}"
        factory = container.orchestrator._sessions._main_factory
        for name in ("capability_registry", "skill_catalog_mode", "_sequencing", "_loop_detector"):
            assert not hasattr(factory, name), f"主 Agent 工厂仍暴露扩展接线: {name}"
        assert getattr(factory, "buyer_skill_store", None) is not None
    finally:
        await container.shutdown()


def test_core_settings_ignore_legacy_extension_environment(monkeypatch, tmp_path):
    _core_environment(monkeypatch, tmp_path)
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("QUEUE_ENABLED", "1")
    monkeypatch.setenv("PROMPT_REGISTRY_ENABLED", "1")
    monkeypatch.setenv("PUBLIC_SKILLS_ENABLED", "1")
    monkeypatch.setenv("HARNESS_ENABLED", "1")
    settings = load_settings()
    assert settings.qdrant_url == ""
    for name in ("redis_url", "queue_enabled", "prompt_registry_enabled",
                 "public_skills_enabled", "harness_enabled"):
        assert not hasattr(settings, name), f"旧环境变量重新暴露扩展配置: {name}"
