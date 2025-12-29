"""
Tests for main module.

Tests:
- Configuration validation
- Agent creation
- Interactive loop commands
- Error handling
"""

from unittest.mock import MagicMock, patch, call
import pytest


class TestMainConfigValidation:
    """Tests for configuration validation in main()."""

    @patch("kube_medic.main.setup_logging")
    @patch("kube_medic.main.get_settings")
    def test_returns_1_on_config_error(self, mock_settings, mock_logging) -> None:
        """Test that main returns 1 when configuration fails."""
        mock_settings.side_effect = Exception("Missing API key")

        from kube_medic.main import main

        result = main()

        assert result == 1

    @patch("kube_medic.main.setup_logging")
    @patch("kube_medic.main.get_settings")
    def test_logs_config_error(self, mock_settings, mock_logging) -> None:
        """Test that configuration errors are logged."""
        mock_settings.side_effect = Exception("Missing API key")

        with patch("kube_medic.main.logger") as mock_logger:
            from kube_medic.main import main

            main()

            # Should log the error
            mock_logger.error.assert_called()


class TestMainAgentCreation:
    """Tests for agent creation in main()."""

    @patch("kube_medic.main.setup_logging")
    @patch("kube_medic.main.get_settings")
    @patch("kube_medic.main.create_supervisor_agent")
    def test_returns_1_on_agent_creation_failure(
            self,
            mock_create_agent,
            mock_settings,
            mock_logging
    ) -> None:
        """Test that main returns 1 when agent creation fails."""
        mock_settings.return_value = MagicMock(prometheus_url="http://test")
        mock_create_agent.side_effect = Exception("LLM connection failed")

        from kube_medic.main import main

        result = main()

        assert result == 1

    @patch("kube_medic.main.setup_logging")
    @patch("kube_medic.main.get_settings")
    @patch("kube_medic.main.create_supervisor_agent")
    def test_creates_agent_with_memory(
            self,
            mock_create_agent,
            mock_settings,
            mock_logging
    ) -> None:
        """Test that agent is created with memory enabled."""
        mock_settings.return_value = MagicMock(prometheus_url="http://test")
        mock_create_agent.return_value = MagicMock()

        with patch("builtins.input", side_effect=["quit"]):
            with patch("builtins.print"):
                from kube_medic.main import main
                main()

        mock_create_agent.assert_called_once_with(use_memory=True)


class TestMainInteractiveLoop:
    """Tests for interactive loop in main()."""

    @patch("kube_medic.main.setup_logging")
    @patch("kube_medic.main.get_settings")
    @patch("kube_medic.main.create_supervisor_agent")
    @patch("kube_medic.main.stream_agent")
    def test_quit_command_exits(
            self,
            mock_stream,
            mock_create_agent,
            mock_settings,
            mock_logging
    ) -> None:
        """Test that 'quit' command exits the loop."""
        mock_settings.return_value = MagicMock(prometheus_url="http://test")
        mock_create_agent.return_value = MagicMock()

        with patch("builtins.input", side_effect=["quit"]):
            with patch("builtins.print"):
                from kube_medic.main import main
                result = main()

        assert result == 0
        mock_stream.assert_not_called()

    @patch("kube_medic.main.setup_logging")
    @patch("kube_medic.main.get_settings")
    @patch("kube_medic.main.create_supervisor_agent")
    @patch("kube_medic.main.stream_agent")
    def test_exit_command_exits(
            self,
            mock_stream,
            mock_create_agent,
            mock_settings,
            mock_logging
    ) -> None:
        """Test that 'exit' command exits the loop."""
        mock_settings.return_value = MagicMock(prometheus_url="http://test")
        mock_create_agent.return_value = MagicMock()

        with patch("builtins.input", side_effect=["exit"]):
            with patch("builtins.print"):
                from kube_medic.main import main
                result = main()

        assert result == 0

    @patch("kube_medic.main.setup_logging")
    @patch("kube_medic.main.get_settings")
    @patch("kube_medic.main.create_supervisor_agent")
    @patch("kube_medic.main.stream_agent")
    def test_q_command_exits(
            self,
            mock_stream,
            mock_create_agent,
            mock_settings,
            mock_logging
    ) -> None:
        """Test that 'q' command exits the loop."""
        mock_settings.return_value = MagicMock(prometheus_url="http://test")
        mock_create_agent.return_value = MagicMock()

        with patch("builtins.input", side_effect=["q"]):
            with patch("builtins.print"):
                from kube_medic.main import main
                result = main()

        assert result == 0

    @patch("kube_medic.main.setup_logging")
    @patch("kube_medic.main.get_settings")
    @patch("kube_medic.main.create_supervisor_agent")
    @patch("kube_medic.main.stream_agent")
    def test_new_command_resets_thread_id(
            self,
            mock_stream,
            mock_create_agent,
            mock_settings,
            mock_logging
    ) -> None:
        """Test that 'new' command starts new conversation."""
        mock_settings.return_value = MagicMock(prometheus_url="http://test")
        mock_create_agent.return_value = MagicMock()

        with patch("builtins.input", side_effect=["new", "quit"]):
            with patch("builtins.print") as mock_print:
                from kube_medic.main import main
                main()

        # Should print message about new conversation
        print_calls = " ".join([str(c) for c in mock_print.call_args_list])
        assert "new conversation" in print_calls.lower()

    @patch("kube_medic.main.setup_logging")
    @patch("kube_medic.main.get_settings")
    @patch("kube_medic.main.create_supervisor_agent")
    @patch("kube_medic.main.stream_agent")
    def test_empty_input_is_skipped(
            self,
            mock_stream,
            mock_create_agent,
            mock_settings,
            mock_logging
    ) -> None:
        """Test that empty input is skipped."""
        mock_settings.return_value = MagicMock(prometheus_url="http://test")
        mock_create_agent.return_value = MagicMock()

        with patch("builtins.input", side_effect=["", "   ", "quit"]):
            with patch("builtins.print"):
                from kube_medic.main import main
                main()

        # stream_agent should not be called for empty inputs
        mock_stream.assert_not_called()

    @patch("kube_medic.main.setup_logging")
    @patch("kube_medic.main.get_settings")
    @patch("kube_medic.main.create_supervisor_agent")
    @patch("kube_medic.main.stream_agent")
    def test_query_calls_stream_agent(
            self,
            mock_stream,
            mock_create_agent,
            mock_settings,
            mock_logging
    ) -> None:
        """Test that user query calls stream_agent."""
        mock_settings.return_value = MagicMock(prometheus_url="http://test")
        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        with patch("builtins.input", side_effect=["check pod status", "quit"]):
            with patch("builtins.print"):
                from kube_medic.main import main
                main()

        # stream_agent should be called with the query
        mock_stream.assert_called_once()
        call_args = mock_stream.call_args
        assert call_args[0][0] is mock_agent
        assert call_args[0][1] == "check pod status"
        assert call_args[1]["verbose"] is True


class TestMainErrorHandling:
    """Tests for error handling in main()."""

    @patch("kube_medic.main.setup_logging")
    @patch("kube_medic.main.get_settings")
    @patch("kube_medic.main.create_supervisor_agent")
    @patch("kube_medic.main.stream_agent")
    def test_keyboard_interrupt_exits_gracefully(
            self,
            mock_stream,
            mock_create_agent,
            mock_settings,
            mock_logging
    ) -> None:
        """Test that Ctrl+C exits gracefully."""
        mock_settings.return_value = MagicMock(prometheus_url="http://test")
        mock_create_agent.return_value = MagicMock()

        with patch("builtins.input", side_effect=KeyboardInterrupt()):
            with patch("builtins.print"):
                from kube_medic.main import main
                result = main()

        assert result == 0

    @patch("kube_medic.main.setup_logging")
    @patch("kube_medic.main.get_settings")
    @patch("kube_medic.main.create_supervisor_agent")
    @patch("kube_medic.main.stream_agent")
    def test_stream_agent_error_is_handled(
            self,
            mock_stream,
            mock_create_agent,
            mock_settings,
            mock_logging
    ) -> None:
        """Test that errors from stream_agent are handled."""
        mock_settings.return_value = MagicMock(prometheus_url="http://test")
        mock_create_agent.return_value = MagicMock()
        mock_stream.side_effect = [Exception("API error"), None]

        with patch("builtins.input", side_effect=["query 1", "quit"]):
            with patch("builtins.print") as mock_print:
                from kube_medic.main import main
                result = main()

        # Should handle error and continue
        assert result == 0
        # Error should be printed
        print_calls = " ".join([str(c) for c in mock_print.call_args_list])
        assert "error" in print_calls.lower()


class TestMainExitCommands:
    """Tests for exit command variations."""

    @patch("kube_medic.main.setup_logging")
    @patch("kube_medic.main.get_settings")
    @patch("kube_medic.main.create_supervisor_agent")
    @patch("kube_medic.main.stream_agent")
    def test_quit_case_insensitive(
            self,
            mock_stream,
            mock_create_agent,
            mock_settings,
            mock_logging
    ) -> None:
        """Test that QUIT (uppercase) also exits."""
        mock_settings.return_value = MagicMock(prometheus_url="http://test")
        mock_create_agent.return_value = MagicMock()

        with patch("builtins.input", side_effect=["QUIT"]):
            with patch("builtins.print"):
                from kube_medic.main import main
                result = main()

        assert result == 0

    @patch("kube_medic.main.setup_logging")
    @patch("kube_medic.main.get_settings")
    @patch("kube_medic.main.create_supervisor_agent")
    @patch("kube_medic.main.stream_agent")
    def test_exit_case_insensitive(
            self,
            mock_stream,
            mock_create_agent,
            mock_settings,
            mock_logging
    ) -> None:
        """Test that EXIT (uppercase) also exits."""
        mock_settings.return_value = MagicMock(prometheus_url="http://test")
        mock_create_agent.return_value = MagicMock()

        with patch("builtins.input", side_effect=["EXIT"]):
            with patch("builtins.print"):
                from kube_medic.main import main
                result = main()

        assert result == 0