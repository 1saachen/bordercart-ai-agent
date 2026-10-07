from app.infrastructure.settings import load_settings


def test_local_runtime_defaults_to_single_process(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("QUEUE_ENABLED", raising=False)
    monkeypatch.delenv("SEMANTIC_CACHE_ENABLED", raising=False)
    monkeypatch.delenv("QUEUE_PRIORITY_ENABLED", raising=False)

    settings = load_settings()

    assert settings.redis_url == ""
    assert settings.queue_enabled is False
    assert settings.semantic_cache_enabled is False
    assert settings.queue_priority_enabled is False


def test_redis_runtime_remains_opt_in(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("QUEUE_ENABLED", "1")
    monkeypatch.setenv("SEMANTIC_CACHE_ENABLED", "1")
    monkeypatch.setenv("QUEUE_PRIORITY_ENABLED", "1")

    settings = load_settings()

    assert settings.redis_url.startswith("redis://")
    assert settings.queue_enabled is True
    assert settings.semantic_cache_enabled is True
    assert settings.queue_priority_enabled is True
