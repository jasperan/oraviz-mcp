#!/usr/bin/env python
"""
Tests for the Oracle Viz MCP application entry point.
"""

from unittest.mock import MagicMock, patch

import pytest

from oraviz_mcp import main
from oraviz_mcp.main import run_server, setup_environment
from oraviz_mcp.server import config


def configure(monkeypatch, **overrides):
    values = dict(user="scott", password="tiger")
    values.update(overrides)
    for key, value in values.items():
        monkeypatch.setattr(config, key, value)


class TestSetupEnvironment:
    def test_success(self, monkeypatch):
        configure(monkeypatch)
        with patch("dotenv.load_dotenv", return_value=False):
            assert setup_environment() is True

    def test_dotenv_loaded(self, monkeypatch):
        configure(monkeypatch)
        with patch("dotenv.load_dotenv", return_value=True):
            with patch.object(main.logger, "info") as mock_logger:
                assert setup_environment() is True
                mock_logger.assert_any_call("Loaded environment variables from .env file")

    def test_missing_user(self, monkeypatch):
        configure(monkeypatch, user="")
        with patch("dotenv.load_dotenv", return_value=False):
            assert setup_environment() is False

    def test_missing_password(self, monkeypatch):
        configure(monkeypatch, password="")
        with patch("dotenv.load_dotenv", return_value=False):
            assert setup_environment() is False

    def test_invalid_transport(self, monkeypatch):
        configure(monkeypatch)
        monkeypatch.setattr(config.mcp_server_config, "mcp_server_transport", "carrier-pigeon")
        with patch("dotenv.load_dotenv", return_value=False):
            assert setup_environment() is False

    def test_invalid_port(self, monkeypatch):
        configure(monkeypatch)
        monkeypatch.setattr(config.mcp_server_config, "mcp_bind_port", 70000)
        with patch("dotenv.load_dotenv", return_value=False):
            assert setup_environment() is False

    def test_logs_connection_summary_without_password(self, monkeypatch):
        configure(monkeypatch)
        with patch("dotenv.load_dotenv", return_value=False):
            with patch.object(main.logger, "info") as mock_logger:
                assert setup_environment() is True
        summary = mock_logger.call_args_list[-1]
        assert summary.args[0] == "Oracle configuration loaded"
        assert "password" not in summary.kwargs
        assert summary.kwargs["user"] == "scott"


class TestRunServer:
    def test_stdio_transport(self, monkeypatch):
        configure(monkeypatch)
        monkeypatch.setattr(config.mcp_server_config, "mcp_server_transport", "stdio")
        recorder = MagicMock()
        monkeypatch.setattr(main.mcp, "run", recorder)
        with patch.object(main, "setup_environment", return_value=True):
            run_server()
        recorder.assert_called_once_with(transport="stdio")

    def test_http_transport(self, monkeypatch):
        configure(monkeypatch)
        monkeypatch.setattr(config.mcp_server_config, "mcp_server_transport", "http")
        monkeypatch.setattr(config.mcp_server_config, "mcp_bind_host", "127.0.0.1")
        monkeypatch.setattr(config.mcp_server_config, "mcp_bind_port", 8080)
        recorder = MagicMock()
        monkeypatch.setattr(main.mcp, "run", recorder)
        with patch.object(main, "setup_environment", return_value=True):
            run_server()
        recorder.assert_called_once_with(transport="http", host="127.0.0.1", port=8080)

    def test_failed_setup_exits(self, monkeypatch):
        configure(monkeypatch)
        with patch.object(main, "setup_environment", return_value=False):
            with pytest.raises(SystemExit):
                run_server()
