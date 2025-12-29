"""
Tests for logging configuration.

Tests:
- Log level parsing
- Environment variable handling
- Handler creation
- Configuration defaults
- Log execution decorator
"""

import logging
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest


class TestParseLogLevel:
    """Tests for log level parsing."""

    def test_parse_debug(self) -> None:
        """Test parsing DEBUG level."""
        from kube_medic.logging_config import _parse_log_level

        assert _parse_log_level("DEBUG") == logging.DEBUG

    def test_parse_info(self) -> None:
        """Test parsing INFO level."""
        from kube_medic.logging_config import _parse_log_level

        assert _parse_log_level("INFO") == logging.INFO

    def test_parse_warning(self) -> None:
        """Test parsing WARNING level."""
        from kube_medic.logging_config import _parse_log_level

        assert _parse_log_level("WARNING") == logging.WARNING

    def test_parse_error(self) -> None:
        """Test parsing ERROR level."""
        from kube_medic.logging_config import _parse_log_level

        assert _parse_log_level("ERROR") == logging.ERROR

    def test_parse_critical(self) -> None:
        """Test parsing CRITICAL level."""
        from kube_medic.logging_config import _parse_log_level

        assert _parse_log_level("CRITICAL") == logging.CRITICAL

    def test_case_insensitive_lowercase(self) -> None:
        """Test that log level parsing is case-insensitive (lowercase)."""
        from kube_medic.logging_config import _parse_log_level

        assert _parse_log_level("debug") == logging.DEBUG
        assert _parse_log_level("info") == logging.INFO

    def test_case_insensitive_mixed(self) -> None:
        """Test that log level parsing is case-insensitive (mixed case)."""
        from kube_medic.logging_config import _parse_log_level

        assert _parse_log_level("Debug") == logging.DEBUG
        assert _parse_log_level("Info") == logging.INFO
        assert _parse_log_level("WaRnInG") == logging.WARNING

    def test_strips_whitespace(self) -> None:
        """Test that whitespace is stripped from log level."""
        from kube_medic.logging_config import _parse_log_level

        assert _parse_log_level("  DEBUG  ") == logging.DEBUG
        assert _parse_log_level("\tINFO\n") == logging.INFO

    def test_invalid_level_raises_error(self) -> None:
        """Test that invalid log levels raise ValueError."""
        from kube_medic.logging_config import _parse_log_level

        with pytest.raises(ValueError) as exc_info:
            _parse_log_level("INVALID_LEVEL")

        assert "Invalid log level" in str(exc_info.value)
        assert "INVALID_LEVEL" in str(exc_info.value)

    def test_invalid_level_shows_valid_options(self) -> None:
        """Test that error message shows valid options."""
        from kube_medic.logging_config import _parse_log_level

        with pytest.raises(ValueError) as exc_info:
            _parse_log_level("INVALID")

        error_msg = str(exc_info.value)
        assert "DEBUG" in error_msg
        assert "INFO" in error_msg
        assert "WARNING" in error_msg


class TestGetConfigFromEnv:
    """Tests for environment configuration loading."""

    def test_defaults_when_env_not_set(self) -> None:
        """Test that default values are used when env vars not set."""
        from kube_medic.logging_config import _get_config_from_env

        with patch.dict(os.environ, {}, clear=True):
            level, log_file, format_style = _get_config_from_env()

            assert level == logging.INFO
            assert log_file is None
            assert format_style == "detailed"

    def test_custom_log_level(self) -> None:
        """Test that custom LOG_LEVEL is loaded."""
        from kube_medic.logging_config import _get_config_from_env

        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}, clear=True):
            level, log_file, format_style = _get_config_from_env()

            assert level == logging.DEBUG

    def test_custom_log_file(self) -> None:
        """Test that custom LOG_FILE is loaded."""
        from kube_medic.logging_config import _get_config_from_env

        with patch.dict(os.environ, {"LOG_FILE": "/var/log/test.log"}, clear=True):
            level, log_file, format_style = _get_config_from_env()

            assert log_file == "/var/log/test.log"

    def test_simple_format(self) -> None:
        """Test that simple format is loaded."""
        from kube_medic.logging_config import _get_config_from_env

        with patch.dict(os.environ, {"LOG_FORMAT": "simple"}, clear=True):
            level, log_file, format_style = _get_config_from_env()

            assert format_style == "simple"

    def test_detailed_format(self) -> None:
        """Test that detailed format is loaded."""
        from kube_medic.logging_config import _get_config_from_env

        with patch.dict(os.environ, {"LOG_FORMAT": "detailed"}, clear=True):
            level, log_file, format_style = _get_config_from_env()

            assert format_style == "detailed"

    def test_invalid_log_level_falls_back_to_info(self) -> None:
        """Test that invalid LOG_LEVEL falls back to INFO."""
        from kube_medic.logging_config import _get_config_from_env

        with patch.dict(os.environ, {"LOG_LEVEL": "INVALID"}, clear=True):
            level, log_file, format_style = _get_config_from_env()

            assert level == logging.INFO

    def test_invalid_format_falls_back_to_detailed(self) -> None:
        """Test that invalid LOG_FORMAT falls back to detailed."""
        from kube_medic.logging_config import _get_config_from_env

        with patch.dict(os.environ, {"LOG_FORMAT": "invalid_format"}, clear=True):
            level, log_file, format_style = _get_config_from_env()

            assert format_style == "detailed"

    def test_all_custom_values(self) -> None:
        """Test loading all custom env vars."""
        from kube_medic.logging_config import _get_config_from_env

        with patch.dict(os.environ, {
            "LOG_LEVEL": "WARNING",
            "LOG_FILE": "app.log",
            "LOG_FORMAT": "simple",
        }, clear=True):
            level, log_file, format_style = _get_config_from_env()

            assert level == logging.WARNING
            assert log_file == "app.log"
            assert format_style == "simple"


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_creates_console_handler(self) -> None:
        """Test that setup_logging creates console handler."""
        from kube_medic.logging_config import setup_logging

        setup_logging(level=logging.INFO)

        root_logger = logging.getLogger()
        assert len(root_logger.handlers) > 0

        # Check at least one handler is a StreamHandler
        stream_handlers = [h for h in root_logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) > 0

    def test_creates_file_handler(self) -> None:
        """Test that setup_logging creates file handler when log_file specified."""
        from kube_medic.logging_config import setup_logging

        with tempfile.NamedTemporaryFile(delete=False, suffix=".log") as tmp:
            setup_logging(level=logging.INFO, log_file=tmp.name)

            root_logger = logging.getLogger()

            # Check for FileHandler
            file_handlers = [h for h in root_logger.handlers if isinstance(h, logging.FileHandler)]
            assert len(file_handlers) > 0

    def test_sets_log_level(self) -> None:
        """Test that setup_logging sets the correct log level."""
        from kube_medic.logging_config import setup_logging

        setup_logging(level=logging.DEBUG)

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_removes_existing_handlers(self) -> None:
        """Test that setup_logging removes existing handlers to avoid duplicates."""
        from kube_medic.logging_config import setup_logging

        # Call setup twice
        setup_logging(level=logging.INFO)
        initial_count = len(logging.getLogger().handlers)

        setup_logging(level=logging.DEBUG)
        final_count = len(logging.getLogger().handlers)

        # Should not accumulate handlers
        assert final_count <= initial_count + 1

    def test_uses_detailed_format(self) -> None:
        """Test that detailed format includes timestamp and module name."""
        from kube_medic.logging_config import setup_logging

        setup_logging(level=logging.INFO, format_style="detailed")

        root_logger = logging.getLogger()
        handler = root_logger.handlers[0]
        formatter = handler.formatter

        assert formatter is not None
        # Detailed format should include asctime and name
        assert "asctime" in formatter._fmt
        assert "name" in formatter._fmt

    def test_uses_simple_format(self) -> None:
        """Test that simple format is minimal."""
        from kube_medic.logging_config import setup_logging

        setup_logging(level=logging.INFO, format_style="simple")

        root_logger = logging.getLogger()
        handler = root_logger.handlers[0]
        formatter = handler.formatter

        assert formatter is not None
        # Simple format should not include asctime
        assert "asctime" not in formatter._fmt

    def test_creates_log_directory(self) -> None:
        """Test that setup_logging creates log directory if needed."""
        from kube_medic.logging_config import setup_logging

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "subdir", "test.log")
            setup_logging(level=logging.INFO, log_file=log_path)

            # Directory should be created
            assert os.path.exists(os.path.dirname(log_path))

    def test_with_file_multiple_handlers(self) -> None:
        """Test that setup_logging creates console + file handler when LOG_FILE set."""
        from kube_medic.logging_config import setup_logging

        with tempfile.NamedTemporaryFile(delete=False, suffix=".log") as tmp:
            setup_logging(level=logging.INFO, log_file=tmp.name)

            root_logger = logging.getLogger()
            # Should have console + file handler
            assert len(root_logger.handlers) >= 2


class TestGetLogger:
    """Tests for get_logger function."""

    def test_returns_logger(self) -> None:
        """Test that get_logger returns a logger instance."""
        from kube_medic.logging_config import get_logger

        logger = get_logger("test_module")

        assert isinstance(logger, logging.Logger)

    def test_returns_named_logger(self) -> None:
        """Test that get_logger returns logger with correct name."""
        from kube_medic.logging_config import get_logger

        logger = get_logger("my.module.name")

        assert logger.name == "my.module.name"

    def test_same_name_returns_same_logger(self) -> None:
        """Test that same name returns same logger instance."""
        from kube_medic.logging_config import get_logger

        logger1 = get_logger("same_module")
        logger2 = get_logger("same_module")

        assert logger1 is logger2


class TestLogExecutionDecorator:
    """Tests for log_execution decorator."""

    def test_logs_function_execution(self) -> None:
        """Test that decorator logs function execution."""
        from kube_medic.logging_config import log_execution

        mock_logger = MagicMock()

        @log_execution(mock_logger)
        def sample_function():
            return "result"

        result = sample_function()

        assert result == "result"
        # Should log at least start and completion
        assert mock_logger.debug.call_count >= 2

    def test_logs_function_name(self) -> None:
        """Test that decorator logs function name."""
        from kube_medic.logging_config import log_execution

        mock_logger = MagicMock()

        @log_execution(mock_logger)
        def my_named_function():
            return True

        my_named_function()

        # Check that function name was logged
        log_calls = [str(call) for call in mock_logger.debug.call_args_list]
        assert any("my_named_function" in call for call in log_calls)

    def test_logs_error_on_exception(self) -> None:
        """Test that decorator logs errors when exception raised."""
        from kube_medic.logging_config import log_execution

        mock_logger = MagicMock()

        @log_execution(mock_logger)
        def failing_function():
            raise ValueError("Something went wrong")

        with pytest.raises(ValueError):
            failing_function()

        # Should log error
        mock_logger.error.assert_called()

    def test_reraises_exception(self) -> None:
        """Test that decorator re-raises the original exception."""
        from kube_medic.logging_config import log_execution

        mock_logger = MagicMock()

        @log_execution(mock_logger)
        def failing_function():
            raise RuntimeError("Original error")

        with pytest.raises(RuntimeError) as exc_info:
            failing_function()

        assert "Original error" in str(exc_info.value)

    def test_works_with_arguments(self) -> None:
        """Test that decorator works with function arguments."""
        from kube_medic.logging_config import log_execution

        mock_logger = MagicMock()

        @log_execution(mock_logger)
        def add_numbers(a, b):
            return a + b

        result = add_numbers(3, 4)

        assert result == 7

    def test_works_with_kwargs(self) -> None:
        """Test that decorator works with keyword arguments."""
        from kube_medic.logging_config import log_execution

        mock_logger = MagicMock()

        @log_execution(mock_logger)
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        result = greet("World", greeting="Hi")

        assert result == "Hi, World!"

    def test_preserves_return_value(self) -> None:
        """Test that decorator preserves the return value."""
        from kube_medic.logging_config import log_execution

        mock_logger = MagicMock()

        @log_execution(mock_logger)
        def return_dict():
            return {"key": "value", "count": 42}

        result = return_dict()

        assert result == {"key": "value", "count": 42}

    def test_logs_completion_on_success(self) -> None:
        """Test that decorator logs completion on successful execution."""
        from kube_medic.logging_config import log_execution

        mock_logger = MagicMock()

        @log_execution(mock_logger)
        def successful_function():
            return "success"

        successful_function()

        # Check for completion log (contains checkmark or "completed")
        log_calls = " ".join([str(call) for call in mock_logger.debug.call_args_list])
        assert "completed" in log_calls.lower()


class TestLoggingIntegration:
    """Integration tests for logging setup."""

    def test_full_logging_workflow(self) -> None:
        """Test complete logging workflow."""
        from kube_medic.logging_config import setup_logging, get_logger

        with tempfile.NamedTemporaryFile(delete=False, suffix=".log", mode='w') as tmp:
            tmp_name = tmp.name

        # Setup logging
        setup_logging(level=logging.DEBUG, log_file=tmp_name)

        # Get logger
        logger = get_logger("test.integration")

        # Log messages
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")

        # Force flush handlers
        for handler in logging.getLogger().handlers:
            handler.flush()

        # Verify file was written
        with open(tmp_name) as f:
            content = f.read()
            assert "Debug message" in content
            assert "Info message" in content
            assert "Warning message" in content

    def test_different_log_levels(self) -> None:
        """Test that log levels filter correctly."""
        from kube_medic.logging_config import setup_logging, get_logger

        with tempfile.NamedTemporaryFile(delete=False, suffix=".log", mode='w') as tmp:
            tmp_name = tmp.name

        # Setup logging at WARNING level
        setup_logging(level=logging.WARNING, log_file=tmp_name)

        logger = get_logger("test.levels")

        # Log at different levels
        logger.debug("Debug should not appear")
        logger.info("Info should not appear")
        logger.warning("Warning should appear")
        logger.error("Error should appear")

        # Force flush
        for handler in logging.getLogger().handlers:
            handler.flush()

        # Verify file contents
        with open(tmp_name) as f:
            content = f.read()
            assert "Debug should not appear" not in content
            assert "Info should not appear" not in content
            assert "Warning should appear" in content
            assert "Error should appear" in content
