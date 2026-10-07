from app.infrastructure.settings import load_settings


async def test_container_uses_core_personal_skill_path_without_registry(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("PROMPT_REGISTRY_ENABLED", raising=False)
    monkeypatch.delenv("PUBLIC_SKILLS_ENABLED", raising=False)
    from app.composition import build_container

    container = await build_container()
    try:
        assert container.backplane is None
        assert container.task_queue is None
        assert container.prompt_registry is None
        assert container.orchestrator._sessions._main_factory.capability_registry is None
        assert container.orchestrator._sessions._main_factory.buyer_skill_store is not None
    finally:
        await container.shutdown()


async def test_local_runtime_does_not_create_optional_harness(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("HARNESS_ENABLED", raising=False)
    from app.composition import build_container

    container = await build_container()
    try:
        factory = container.orchestrator._sessions._main_factory
        assert container.settings.harness_enabled is False
        assert factory._sequencing is None
        assert factory._loop_detector is None
        assert factory._search_factory._loop_detector is None
        assert factory._trade_factory._loop_detector is None
    finally:
        await container.shutdown()


def test_local_runtime_defaults_to_single_process(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("QUEUE_ENABLED", raising=False)
    monkeypatch.delenv("SEMANTIC_CACHE_ENABLED", raising=False)
    monkeypatch.delenv("QUEUE_PRIORITY_ENABLED", raising=False)
    monkeypatch.delenv("PROMPT_REGISTRY_ENABLED", raising=False)
    monkeypatch.delenv("PUBLIC_SKILLS_ENABLED", raising=False)
    monkeypatch.delenv("HARNESS_ENABLED", raising=False)
    monkeypatch.delenv("RERANKER_MODE", raising=False)

    settings = load_settings()

    assert settings.redis_url == ""
    assert settings.queue_enabled is False
    assert settings.semantic_cache_enabled is False
    assert settings.queue_priority_enabled is False
    assert settings.prompt_registry_enabled is False
    assert settings.public_skills_enabled is False
    assert settings.harness_enabled is False
    assert settings.reranker_mode == "disabled"


def test_redis_runtime_remains_opt_in(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("QUEUE_ENABLED", "1")
    monkeypatch.setenv("SEMANTIC_CACHE_ENABLED", "1")
    monkeypatch.setenv("QUEUE_PRIORITY_ENABLED", "1")
    monkeypatch.setenv("PROMPT_REGISTRY_ENABLED", "1")
    monkeypatch.setenv("PUBLIC_SKILLS_ENABLED", "1")

    settings = load_settings()

    assert settings.redis_url.startswith("redis://")
    assert settings.queue_enabled is True
    assert settings.semantic_cache_enabled is True
    assert settings.queue_priority_enabled is True
    assert settings.prompt_registry_enabled is True
    assert settings.public_skills_enabled is True
