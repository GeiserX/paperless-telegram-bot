"""Tests for configuration module."""

import logging

import pytest

from paperless_bot.config import Config, setup_logging


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
    assert config.remove_inbox_on_done is True
    assert config.inbox_tag is None


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


def test_remove_inbox_on_done_disabled(monkeypatch):
    monkeypatch.setenv("REMOVE_INBOX_ON_DONE", "false")
    config = Config()
    assert config.remove_inbox_on_done is False


def test_remove_inbox_on_done_enabled(monkeypatch):
    monkeypatch.setenv("REMOVE_INBOX_ON_DONE", "true")
    config = Config()
    assert config.remove_inbox_on_done is True


def test_inbox_tag_override(monkeypatch):
    monkeypatch.setenv("INBOX_TAG", "Para Revisar")
    config = Config()
    assert config.inbox_tag == "Para Revisar"


def test_inbox_tag_empty(monkeypatch):
    monkeypatch.setenv("INBOX_TAG", "  ")
    config = Config()
    assert config.inbox_tag is None


def test_setup_logging():
    config = Config()
    setup_logging(config)
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
    assert logging.getLogger("telegram").level == logging.WARNING


def test_paperless_public_url_default():
    config = Config()
    assert config.paperless_public_url == "http://localhost:8000"


def test_paperless_public_url_override(monkeypatch):
    monkeypatch.setenv("PAPERLESS_PUBLIC_URL", "https://papers.example.com/")
    config = Config()
    assert config.paperless_public_url == "https://papers.example.com"


def test_upload_task_timeout_default():
    config = Config()
    assert config.upload_task_timeout == 300


def test_upload_task_timeout_custom(monkeypatch):
    monkeypatch.setenv("UPLOAD_TASK_TIMEOUT", "600")
    config = Config()
    assert config.upload_task_timeout == 600


def test_health_port_custom(monkeypatch):
    monkeypatch.setenv("HEALTH_PORT", "9090")
    config = Config()
    assert config.health_port == 9090


def test_log_level_debug(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    config = Config()
    assert config.log_level == logging.DEBUG


def test_log_level_invalid(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "INVALID")
    config = Config()
    assert config.log_level == logging.INFO  # Falls back to INFO


def test_missing_paperless_token(monkeypatch):
    monkeypatch.delenv("PAPERLESS_TOKEN", raising=False)
    with pytest.raises(ValueError, match="PAPERLESS_TOKEN"):
        Config()


def test_parse_id_set_whitespace():
    result = Config._parse_id_set("  123 , 456 , 789  ")
    assert result == {123, 456, 789}


def test_parse_id_set_trailing_comma():
    result = Config._parse_id_set("123,456,")
    assert result == {123, 456}
