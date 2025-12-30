"""
Tests for Email specialist agent.

Tests:
- System prompt content
- Agent creation
- Tool binding
"""

from unittest.mock import MagicMock, patch


class TestEmailSystemPrompt:
    """Tests for Email agent system prompt."""

    def test_prompt_mentions_email(self) -> None:
        """Test that system prompt mentions email."""
        from kube_medic.agents.email_agent import EMAIL_SYSTEM_PROMPT

        assert "email" in EMAIL_SYSTEM_PROMPT.lower()

    def test_prompt_mentions_all_tools(self) -> None:
        """Test that system prompt mentions all available tools."""
        from kube_medic.agents.email_agent import EMAIL_SYSTEM_PROMPT

        expected_tools = [
            "send_email",
        ]

        for tool in expected_tools:
            assert tool in EMAIL_SYSTEM_PROMPT, f"Tool {tool} not in prompt"

    def test_prompt_describes_agent_role(self) -> None:
        """Test that prompt describes the agent's role."""
        from kube_medic.agents.email_agent import EMAIL_SYSTEM_PROMPT

        assert "specialist" in EMAIL_SYSTEM_PROMPT.lower()

    def test_prompt_has_efficiency_rule(self) -> None:
        """Test that prompt has efficiency rule."""
        from kube_medic.agents.email_agent import EMAIL_SYSTEM_PROMPT

        assert "Efficient rule" in EMAIL_SYSTEM_PROMPT
        assert "ONCE" in EMAIL_SYSTEM_PROMPT

    def test_prompt_mentions_investigation_reports(self) -> None:
        """Test that prompt mentions sending investigation reports."""
        from kube_medic.agents.email_agent import EMAIL_SYSTEM_PROMPT

        assert "investigation" in EMAIL_SYSTEM_PROMPT.lower()
        assert "report" in EMAIL_SYSTEM_PROMPT.lower()


class TestCreateEmailAgent:
    """Tests for create_email_agent function."""

    @patch("kube_medic.agents.email_agent.create_agent")
    @patch("kube_medic.agents.email_agent.get_llm")
    def test_creates_agent_with_llm(self, mock_get_llm, mock_create_agent) -> None:
        """Test that agent is created with LLM from get_llm()."""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        mock_create_agent.return_value = MagicMock()

        from kube_medic.agents.email_agent import create_email_agent

        create_email_agent()

        mock_get_llm.assert_called_once()
        # Verify LLM is passed to create_agent
        call_kwargs = mock_create_agent.call_args[1]
        assert call_kwargs["model"] is mock_llm

    @patch("kube_medic.agents.email_agent.create_agent")
    @patch("kube_medic.agents.email_agent.get_llm")
    def test_creates_agent_with_email_tools(self, mock_get_llm, mock_create_agent) -> None:
        """Test that agent is created with email_tools."""
        mock_get_llm.return_value = MagicMock()
        mock_create_agent.return_value = MagicMock()

        from kube_medic.agents.email_agent import create_email_agent
        from kube_medic.tools.email import email_tools

        create_email_agent()

        call_kwargs = mock_create_agent.call_args[1]
        assert call_kwargs["tools"] is email_tools

    @patch("kube_medic.agents.email_agent.create_agent")
    @patch("kube_medic.agents.email_agent.get_llm")
    def test_creates_agent_with_system_prompt(self, mock_get_llm, mock_create_agent) -> None:
        """Test that agent is created with correct system prompt."""
        mock_get_llm.return_value = MagicMock()
        mock_create_agent.return_value = MagicMock()

        from kube_medic.agents.email_agent import (
            create_email_agent,
            EMAIL_SYSTEM_PROMPT,
        )

        create_email_agent()

        call_kwargs = mock_create_agent.call_args[1]
        assert call_kwargs["system_prompt"] == EMAIL_SYSTEM_PROMPT

    @patch("kube_medic.agents.email_agent.create_agent")
    @patch("kube_medic.agents.email_agent.get_llm")
    def test_returns_agent(self, mock_get_llm, mock_create_agent) -> None:
        """Test that function returns the created agent."""
        mock_get_llm.return_value = MagicMock()
        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        from kube_medic.agents.email_agent import create_email_agent

        result = create_email_agent()

        assert result is mock_agent


class TestEmailToolsIntegration:
    """Tests for email tools integration."""

    def test_email_tools_has_expected_count(self) -> None:
        """Test that email_tools has expected number of tools."""
        from kube_medic.tools.email import email_tools

        assert len(email_tools) == 1

    def test_email_tools_have_names(self) -> None:
        """Test that all email tools have proper names."""
        from kube_medic.tools.email import email_tools

        expected_names = ["send_email"]
        tool_names = [t.name for t in email_tools]

        for name in expected_names:
            assert name in tool_names
