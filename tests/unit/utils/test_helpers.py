"""
Tests for helper utilities.

Tests:
- Error formatting
- Text truncation
- Agent response handling
- Time parsing
- LLM singleton
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


class TestFormatError:
    """Tests for format_error function."""

    def test_format_error(self) -> None:
        """Test that format_error formats exceptions correctly."""
        from kube_medic.utils.helpers import format_error

        error = ValueError("Something went wrong")
        result = format_error(error)

        assert "ValueError" in result
        assert "Something went wrong" in result

    def test_format_error_with_special_chars(self) -> None:
        """Test error formatting with special characters."""
        from kube_medic.utils.helpers import format_error

        error = RuntimeError("Error: Connection refused (localhost:9090)")
        result = format_error(error)

        assert "RuntimeError" in result
        assert "Connection refused" in result

    def test_format_error_custom_exception(self) -> None:
        """Test formatting custom exception."""
        from kube_medic.utils.helpers import format_error

        class CustomError(Exception):
            pass

        error = CustomError("custom message")
        result = format_error(error)

        assert "CustomError" in result
        assert "custom message" in result


class TestTruncateText:
    """Tests for truncate_text function."""

    def test_truncate_text_short(self) -> None:
        """Test that short text is not truncated."""
        from kube_medic.utils.helpers import truncate_text

        text = "Hello, world!"
        result = truncate_text(text, max_length=100)

        assert result == text
        assert "..." not in result

    def test_truncate_text_long(self) -> None:
        """Test that long text is truncated."""
        from kube_medic.utils.helpers import truncate_text

        text = "A" * 100
        result = truncate_text(text, max_length=20)

        assert len(result) == 23  # 20 + "..."
        assert result.endswith("...")
        assert result.startswith("A" * 20)

    def test_truncate_text_exact_length(self) -> None:
        """Test text exactly at max length."""
        from kube_medic.utils.helpers import truncate_text

        text = "A" * 50
        result = truncate_text(text, max_length=50)

        assert result == text
        assert "..." not in result

    def test_truncate_text_with_newlines(self) -> None:
        """Test truncation of text with newlines."""
        from kube_medic.utils.helpers import truncate_text

        text = "Line 1\nLine 2\nLine 3\n" * 10
        result = truncate_text(text, max_length=30)

        assert len(result) == 33  # 30 + "..."
        assert result.endswith("...")

    def test_truncate_text_using_config_default(self) -> None:
        """Test that truncate_text uses config default when max_length=None."""
        from kube_medic.utils.helpers import truncate_text

        text = "X" * 1000

        with patch("kube_medic.utils.helpers.get_settings") as mock_settings:
            mock_settings.return_value.text_truncate_max_length = 100
            result = truncate_text(text, max_length=None)

            assert len(result) == 103  # 100 + "..."
            assert result.endswith("...")


class TestParseRelativeTime:
    """Tests for parse_relative_time function."""

    def test_parse_now(self) -> None:
        """Test parsing 'now' returns current time."""
        from kube_medic.utils.helpers import parse_relative_time

        before = datetime.now()
        result = parse_relative_time("now")
        after = datetime.now()

        assert before <= result <= after

    def test_parse_seconds(self) -> None:
        """Test parsing seconds (e.g., '30s')."""
        from kube_medic.utils.helpers import parse_relative_time

        before = datetime.now()
        result = parse_relative_time("30s")

        expected = before - timedelta(seconds=30)
        diff = abs((result - expected).total_seconds())

        assert diff < 1  # Allow 1 second tolerance

    def test_parse_minutes(self) -> None:
        """Test parsing minutes (e.g., '5m')."""
        from kube_medic.utils.helpers import parse_relative_time

        before = datetime.now()
        result = parse_relative_time("5m")

        expected = before - timedelta(minutes=5)
        diff = abs((result - expected).total_seconds())

        assert diff < 1

    def test_parse_hours(self) -> None:
        """Test parsing hours (e.g., '1h')."""
        from kube_medic.utils.helpers import parse_relative_time

        before = datetime.now()
        result = parse_relative_time("1h")

        expected = before - timedelta(hours=1)
        diff = abs((result - expected).total_seconds())

        assert diff < 1

    def test_parse_days(self) -> None:
        """Test parsing days (e.g., '2d')."""
        from kube_medic.utils.helpers import parse_relative_time

        before = datetime.now()
        result = parse_relative_time("2d")

        expected = before - timedelta(days=2)
        diff = abs((result - expected).total_seconds())

        assert diff < 1

    def test_parse_weeks(self) -> None:
        """Test parsing weeks (e.g., '1w')."""
        from kube_medic.utils.helpers import parse_relative_time

        before = datetime.now()
        result = parse_relative_time("1w")

        expected = before - timedelta(weeks=1)
        diff = abs((result - expected).total_seconds())

        assert diff < 1

    def test_parse_iso_timestamp(self) -> None:
        """Test parsing ISO format timestamp."""
        from kube_medic.utils.helpers import parse_relative_time

        iso_string = "2024-01-15T10:30:00"
        result = parse_relative_time(iso_string)

        expected = datetime(2024, 1, 15, 10, 30, 0)
        assert result == expected

    def test_parse_iso_timestamp_with_microseconds(self) -> None:
        """Test parsing ISO format with microseconds."""
        from kube_medic.utils.helpers import parse_relative_time

        iso_string = "2024-01-15T10:30:00.123456"
        result = parse_relative_time(iso_string)

        expected = datetime(2024, 1, 15, 10, 30, 0, 123456)
        assert result == expected

    def test_invalid_format_raises_error(self) -> None:
        """Test that invalid format raises ValueError."""
        from kube_medic.utils.helpers import parse_relative_time

        with pytest.raises(ValueError) as exc_info:
            parse_relative_time("invalid")

        assert "Invalid time format" in str(exc_info.value)

    def test_invalid_unit_raises_error(self) -> None:
        """Test that invalid unit raises ValueError."""
        from kube_medic.utils.helpers import parse_relative_time

        with pytest.raises(ValueError) as exc_info:
            parse_relative_time("5x")  # 'x' is not a valid unit

        assert "Invalid time format" in str(exc_info.value)

    def test_empty_string_raises_error(self) -> None:
        """Test that empty string raises ValueError."""
        from kube_medic.utils.helpers import parse_relative_time

        with pytest.raises(ValueError):
            parse_relative_time("")

    def test_large_values(self) -> None:
        """Test parsing large time values."""
        from kube_medic.utils.helpers import parse_relative_time

        result = parse_relative_time("100d")
        expected = datetime.now() - timedelta(days=100)
        diff = abs((result - expected).total_seconds())

        assert diff < 1


class TestGetLlm:
    """Tests for get_llm singleton function."""

    @patch("kube_medic.utils.helpers.AzureChatOpenAI")
    @patch("kube_medic.utils.helpers.get_settings")
    def test_get_llm_creates_instance(self, mock_settings, mock_azure) -> None:
        """Test that get_llm creates an LLM instance."""
        from kube_medic.utils.helpers import get_llm
        import kube_medic.utils.helpers as helpers_module

        # Reset singleton
        helpers_module._llm_instance = None

        # Setup mock settings
        mock_settings.return_value = MagicMock(
            azure_openai_endpoint="https://test.openai.azure.com",
            azure_openai_api_key="test-key",
            azure_openai_deployment_name="gpt-4",
            azure_openai_api_version="2024-08-01-preview",
            llm_temperature=0.0,
            llm_max_tokens=2048,
        )

        # Call get_llm
        result = get_llm()

        # Verify AzureChatOpenAI was called with correct params
        mock_azure.assert_called_once_with(
            azure_endpoint="https://test.openai.azure.com",
            api_key="test-key",
            azure_deployment="gpt-4",
            api_version="2024-08-01-preview",
            temperature=0.0,
            max_tokens=2048,
        )

        assert result is not None

    @patch("kube_medic.utils.helpers.AzureChatOpenAI")
    @patch("kube_medic.utils.helpers.get_settings")
    def test_get_llm_returns_singleton(self, mock_settings, mock_azure) -> None:
        """Test that get_llm returns the same instance on subsequent calls."""
        from kube_medic.utils.helpers import get_llm
        import kube_medic.utils.helpers as helpers_module

        # Reset singleton
        helpers_module._llm_instance = None

        mock_settings.return_value = MagicMock(
            azure_openai_endpoint="https://test.openai.azure.com",
            azure_openai_api_key="test-key",
            azure_openai_deployment_name="gpt-4",
            azure_openai_api_version="2024-08-01-preview",
            llm_temperature=0.0,
            llm_max_tokens=2048,
        )

        # Call twice
        result1 = get_llm()
        result2 = get_llm()

        # Should be same instance
        assert result1 is result2

        # AzureChatOpenAI should only be called once
        assert mock_azure.call_count == 1


class TestAskAgent:
    """Tests for ask_agent function."""

    def test_returns_final_response(self) -> None:
        """Test that ask_agent returns the final AI response."""
        from kube_medic.utils.helpers import ask_agent

        mock_agent = MagicMock()

        # Create mock final response message
        mock_message = MagicMock()
        mock_message.content = "Investigation complete"
        mock_message.type = "ai"
        mock_message.tool_calls = None

        mock_agent.stream.return_value = [
            {"agent": {"messages": [mock_message]}}
        ]

        with patch("kube_medic.utils.helpers.get_settings") as mock_settings:
            mock_settings.return_value.agent_recursion_limit = 50
            result = ask_agent(mock_agent, "query")

        assert result == "Investigation complete"

    def test_uses_thread_id(self) -> None:
        """Test that ask_agent passes thread_id in config."""
        from kube_medic.utils.helpers import ask_agent

        mock_agent = MagicMock()
        mock_agent.stream.return_value = []

        with patch("kube_medic.utils.helpers.get_settings") as mock_settings:
            mock_settings.return_value.agent_recursion_limit = 50
            ask_agent(mock_agent, "query", thread_id="test-thread")

        call_args = mock_agent.stream.call_args
        config = call_args[1]["config"]
        assert config["configurable"]["thread_id"] == "test-thread"

    def test_uses_recursion_limit_from_config(self) -> None:
        """Test that ask_agent passes recursion_limit from settings."""
        from kube_medic.utils.helpers import ask_agent

        mock_agent = MagicMock()
        mock_agent.stream.return_value = []

        with patch("kube_medic.utils.helpers.get_settings") as mock_settings:
            mock_settings.return_value.agent_recursion_limit = 100
            ask_agent(mock_agent, "query")

        call_args = mock_agent.stream.call_args
        config = call_args[1]["config"]
        assert config["recursion_limit"] == 100

    def test_handles_tool_calls(self) -> None:
        """Test that ask_agent handles tool call messages."""
        from kube_medic.utils.helpers import ask_agent

        mock_agent = MagicMock()

        # Tool call message
        tool_call_msg = MagicMock()
        tool_call_msg.content = "Let me check..."
        tool_call_msg.type = "ai"
        tool_call_msg.tool_calls = [{"name": "list_pods", "args": {"namespace": "default"}}]

        # Tool result message
        tool_result_msg = MagicMock()
        tool_result_msg.content = "Pod: nginx-abc123"
        tool_result_msg.type = "tool"
        tool_result_msg.name = "list_pods"

        # Final response
        final_msg = MagicMock()
        final_msg.content = "Found pod nginx-abc123"
        final_msg.type = "ai"
        final_msg.tool_calls = None

        mock_agent.stream.return_value = [
            {"agent": {"messages": [tool_call_msg]}},
            {"tools": {"messages": [tool_result_msg]}},
            {"agent": {"messages": [final_msg]}},
        ]

        with patch("kube_medic.utils.helpers.get_settings") as mock_settings:
            mock_settings.return_value.agent_recursion_limit = 50
            result = ask_agent(mock_agent, "query")

        assert result == "Found pod nginx-abc123"

    def test_returns_default_on_empty_response(self) -> None:
        """Test that ask_agent returns default when no response."""
        from kube_medic.utils.helpers import ask_agent

        mock_agent = MagicMock()
        mock_agent.stream.return_value = []

        with patch("kube_medic.utils.helpers.get_settings") as mock_settings:
            mock_settings.return_value.agent_recursion_limit = 50
            result = ask_agent(mock_agent, "query")

        assert result == "No response from agent."
