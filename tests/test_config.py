"""Tests for configuration module."""

import pytest

from paperless_bot.config import Config


@pytest.fixture(autouse=True)
def _set_required_env(monkeypatch):
    """Set minimum required env vars for Config."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("PAPERLESS_URL", "http://localhost:8000")
    monkeypatch.setenv("PAPERLESS_TOKEN", "test-api-token")


def test_loads_required_vars():
    config = Config()
    assert config.telegram_bot_token == "test-token"
    assert config.paperless_url == "http://localhost:8000"
    assert config.paperless_token == "test-api-token"


def test_default_values():
    config = Config()
    assert config.max_search_results == 10
    assert config.health_port == 8080
    assert config.telegram_allowed_users == set()


def test_allowed_users_parsing(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ALLOWED_USERS", "123,456,789")
    config = Config()
    assert config.telegram_allowed_users == {123, 456, 789}


def test_allowed_users_empty(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ALLOWED_USERS", "")
    config = Config()
    assert config.telegram_allowed_users == set()


def test_missing_required_var(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        Config()


def test_missing_paperless_url(monkeypatch):
    monkeypatch.delenv("PAPERLESS_URL", raising=False)
    with pytest.raises(ValueError, match="PAPERLESS_URL"):
        Config()


def test_custom_search_results(monkeypatch):
    monkeypatch.setenv("MAX_SEARCH_RESULTS", "5")
    config = Config()
    assert config.max_search_results == 5


def test_log_level_warn_alias(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "WARN")
    config = Config()
    assert config.log_level == 30  # logging.WARNING
