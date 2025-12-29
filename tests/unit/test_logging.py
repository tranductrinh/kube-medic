"""
Tests for logging configuration.

Tests:
- Log level parsing
- Environment variable handling
- Handler creation
- Configuration defaults
"""

import logging
import os
from unittest.mock import patch

import pytest


class TestLogging:
    """Tests for logging configuration."""

    def test_parse_log_level_valid(self) -> None:
        """Test parsing valid log level strings."""
        from kube_medic.logging_config import _parse_log_level

        assert _parse_log_level("DEBUG") == logging.DEBUG
        assert _parse_log_level("INFO") == logging.INFO
        assert _parse_log_level("WARNING") == logging.WARNING
        assert _parse_log_level("ERROR") == logging.ERROR
        assert _parse_log_level("CRITICAL") == logging.CRITICAL

    def test_parse_log_level_case_insensitive(self) -> None:
        """Test that log level parsing is case-insensitive."""
        from kube_medic.logging_config import _parse_log_level

        assert _parse_log_level("debug") == logging.DEBUG
        assert _parse_log_level("Info") == logging.INFO
        assert _parse_log_level("WARNING") == logging.WARNING

    def test_parse_log_level_invalid(self) -> None:
        """Test that invalid log levels raise ValueError."""
        from kube_medic.logging_config import _parse_log_level

        with pytest.raises(ValueError) as exc_info:
            _parse_log_level("INVALID_LEVEL")

        assert "Invalid log level" in str(exc_info.value)

    def test_get_config_from_env_defaults(self) -> None:
        """Test that default values are used when env vars not set."""
        from kube_medic.logging_config import _get_config_from_env

        with patch.dict(os.environ, {}, clear=True):
            level, log_file, format_style = _get_config_from_env()

            assert level == logging.INFO  # default
            assert log_file is None  # default
            assert format_style == "detailed"  # default

    def test_get_config_from_env_custom(self) -> None:
        """Test that custom env vars override defaults."""
        from kube_medic.logging_config import _get_config_from_env

        with patch.dict(os.environ, {
            "LOG_LEVEL": "DEBUG",
            "LOG_FILE": "test.log",
            "LOG_FORMAT": "simple",
        }):
            level, log_file, format_style = _get_config_from_env()

            assert level == logging.DEBUG
            assert log_file == "test.log"
            assert format_style == "simple"

    def test_setup_logging_creates_handlers(self) -> None:
        """Test that setup_logging creates proper handlers."""
        from kube_medic.logging_config import setup_logging

        setup_logging(level=logging.INFO)

        root_logger = logging.getLogger()
        assert len(root_logger.handlers) > 0  # At least console handler

    def test_setup_logging_with_file(self) -> None:
        """Test that setup_logging creates file handler when LOG_FILE set."""
        from kube_medic.logging_config import setup_logging
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            setup_logging(level=logging.INFO, log_file=tmp.name)

            root_logger = logging.getLogger()
            # Should have console + file handler
            assert len(root_logger.handlers) >= 2

