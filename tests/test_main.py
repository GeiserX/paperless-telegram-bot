"""Tests for __main__ module (entry point, health server, CLI)."""

from unittest.mock import MagicMock, patch

import pytest

from paperless_bot import __version__
from paperless_bot.__main__ import cmd_run, create_health_app, main, run_health_server

# ---------------------------------------------------------------------------
# Health app
# ---------------------------------------------------------------------------


class TestHealthApp:
    def test_creates_fastapi_app(self):
        app = create_health_app()
        assert app.title == "Paperless Telegram Bot"
        assert app.version == __version__
        # docs disabled
        assert app.docs_url is None
        assert app.redoc_url is None

    def test_health_route_registered(self):
        app = create_health_app()
        routes = [r.path for r in app.routes]
        assert "/health" in routes


# ---------------------------------------------------------------------------
# run_health_server
# ---------------------------------------------------------------------------


class TestRunHealthServer:
    def test_starts_uvicorn(self):
        with (
            patch("paperless_bot.__main__.create_health_app") as mock_app,
            patch("paperless_bot.__main__.uvicorn") as mock_uvicorn,
        ):
            mock_server = MagicMock()
            mock_uvicorn.Config.return_value = MagicMock()
            mock_uvicorn.Server.return_value = mock_server

            run_health_server(8080)

            mock_app.assert_called_once()
            mock_uvicorn.Config.assert_called_once()
            mock_uvicorn.Server.assert_called_once()
            mock_server.run.assert_called_once()


# ---------------------------------------------------------------------------
# cmd_run
# ---------------------------------------------------------------------------


class TestCmdRun:
    def test_cmd_run_starts_bot(self):
        with (
            patch("paperless_bot.__main__.Config") as mock_config_cls,
            patch("paperless_bot.__main__.setup_logging") as mock_logging,
            patch("paperless_bot.__main__.create_bot") as mock_create_bot,
            patch("threading.Thread") as mock_thread,
        ):
            mock_config = MagicMock()
            mock_config.health_port = 8080
            mock_config_cls.return_value = mock_config

            mock_app = MagicMock()
            mock_create_bot.return_value = mock_app

            cmd_run(MagicMock())

            mock_config_cls.assert_called_once()
            mock_logging.assert_called_once_with(mock_config)
            mock_thread.assert_called_once()
            mock_thread.return_value.start.assert_called_once()
            mock_create_bot.assert_called_once_with(mock_config)
            mock_app.run_polling.assert_called_once_with(drop_pending_updates=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCLI:
    def test_version(self, capsys):
        with pytest.raises(SystemExit) as exc_info, patch("sys.argv", ["paperless-bot", "--version"]):
            main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert __version__ in captured.out

    def test_unknown_command(self):
        with pytest.raises(SystemExit) as exc_info, patch("sys.argv", ["paperless-bot", "unknown"]):
            main()
        assert exc_info.value.code != 0

    def test_default_command_calls_run(self):
        with patch("sys.argv", ["paperless-bot"]), patch("paperless_bot.__main__.cmd_run") as mock_run:
            main()
            mock_run.assert_called_once()

    def test_run_command_calls_run(self):
        with patch("sys.argv", ["paperless-bot", "run"]), patch("paperless_bot.__main__.cmd_run") as mock_run:
            main()
            mock_run.assert_called_once()
