"""Unit tests for RedisSettings and redis_url property compatibility."""

import pytest
from backend.core.config.redis import RedisSettings


def test_redis_settings_default_url(monkeypatch):
    monkeypatch.delenv("REDIS_HOST", raising=False)
    monkeypatch.delenv("REDIS_PORT", raising=False)
    monkeypatch.delenv("REDIS_PASSWORD", raising=False)
    monkeypatch.delenv("REDIS_DB", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    settings = RedisSettings(_env_file=None, host="localhost", port=6379, db=0, password="")
    assert settings.url == "redis://localhost:6379/0"
    assert settings.redis_url == settings.url


def test_redis_settings_with_password(monkeypatch):
    monkeypatch.delenv("REDIS_HOST", raising=False)
    monkeypatch.delenv("REDIS_PORT", raising=False)
    monkeypatch.delenv("REDIS_PASSWORD", raising=False)
    monkeypatch.delenv("REDIS_DB", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    settings = RedisSettings(_env_file=None, host="10.0.0.1", port=6380, password="secret_pass", db=2)
    assert settings.url == "redis://:secret_pass@10.0.0.1:6380/2"
    assert settings.redis_url == settings.url


def test_redis_settings_url_override(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    settings = RedisSettings(_env_file=None, url_override="redis://custom-redis:6379/5")
    assert settings.url == "redis://custom-redis:6379/5"
    assert settings.redis_url == "redis://custom-redis:6379/5"


def test_redis_settings_redis_url_matches_url():
    settings = RedisSettings()
    assert settings.redis_url == settings.url
