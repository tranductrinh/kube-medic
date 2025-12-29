"""
Tests for Prometheus specialist agent.

Tests:
- System prompt content
- Agent creation
- Tool binding
"""

from unittest.mock import MagicMock, patch


class TestPrometheusSystemPrompt:
    """Tests for Prometheus agent system prompt."""

    def test_prompt_mentions_prometheus(self) -> None:
        """Test that system prompt mentions Prometheus."""
        from kube_medic.agents.prometheus_agent import PROMETHEUS_SYSTEM_PROMPT

        assert "Prometheus" in PROMETHEUS_SYSTEM_PROMPT

    def test_prompt_mentions_all_tools(self) -> None:
        """Test that system prompt mentions all available tools."""
        from kube_medic.agents.prometheus_agent import PROMETHEUS_SYSTEM_PROMPT

        expected_tools = [
            "prometheus_query",
            "prometheus_query_range",
        ]

        for tool in expected_tools:
            assert tool in PROMETHEUS_SYSTEM_PROMPT, f"Tool {tool} not in prompt"

    def test_prompt_has_important_instruction(self) -> None:
        """Test that prompt has IMPORTANT instruction for supervisor."""
        from kube_medic.agents.prometheus_agent import PROMETHEUS_SYSTEM_PROMPT

        assert "IMPORTANT" in PROMETHEUS_SYSTEM_PROMPT
        assert "supervisor" in PROMETHEUS_SYSTEM_PROMPT.lower()

    def test_prompt_describes_agent_role(self) -> None:
        """Test that prompt describes the agent's role."""
        from kube_medic.agents.prometheus_agent import PROMETHEUS_SYSTEM_PROMPT

        assert "expert" in PROMETHEUS_SYSTEM_PROMPT.lower()
        assert "metrics" in PROMETHEUS_SYSTEM_PROMPT.lower()

    def test_prompt_mentions_promql(self) -> None:
        """Test that prompt mentions PromQL for custom queries."""
        from kube_medic.agents.prometheus_agent import PROMETHEUS_SYSTEM_PROMPT

        assert "PromQL" in PROMETHEUS_SYSTEM_PROMPT


class TestCreatePrometheusAgent:
    """Tests for create_prometheus_agent function."""

    @patch("kube_medic.agents.prometheus_agent.create_agent")
    @patch("kube_medic.agents.prometheus_agent.get_llm")
    def test_creates_agent_with_llm(self, mock_get_llm, mock_create_agent) -> None:
        """Test that agent is created with LLM from get_llm()."""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        mock_create_agent.return_value = MagicMock()

        from kube_medic.agents.prometheus_agent import create_prometheus_agent

        create_prometheus_agent()

        mock_get_llm.assert_called_once()
        # Verify LLM is passed to create_agent
        call_kwargs = mock_create_agent.call_args[1]
        assert call_kwargs["model"] is mock_llm

    @patch("kube_medic.agents.prometheus_agent.create_agent")
    @patch("kube_medic.agents.prometheus_agent.get_llm")
    def test_creates_agent_with_prometheus_tools(self, mock_get_llm, mock_create_agent) -> None:
        """Test that agent is created with prometheus_tools."""
        mock_get_llm.return_value = MagicMock()
        mock_create_agent.return_value = MagicMock()

        from kube_medic.agents.prometheus_agent import create_prometheus_agent
        from kube_medic.tools.prometheus import prometheus_tools

        create_prometheus_agent()

        call_kwargs = mock_create_agent.call_args[1]
        assert call_kwargs["tools"] is prometheus_tools

    @patch("kube_medic.agents.prometheus_agent.create_agent")
    @patch("kube_medic.agents.prometheus_agent.get_llm")
    def test_creates_agent_with_system_prompt(self, mock_get_llm, mock_create_agent) -> None:
        """Test that agent is created with correct system prompt."""
        mock_get_llm.return_value = MagicMock()
        mock_create_agent.return_value = MagicMock()

        from kube_medic.agents.prometheus_agent import (
            create_prometheus_agent,
            PROMETHEUS_SYSTEM_PROMPT,
        )

        create_prometheus_agent()

        call_kwargs = mock_create_agent.call_args[1]
        assert call_kwargs["system_prompt"] == PROMETHEUS_SYSTEM_PROMPT

    @patch("kube_medic.agents.prometheus_agent.create_agent")
    @patch("kube_medic.agents.prometheus_agent.get_llm")
    def test_returns_agent(self, mock_get_llm, mock_create_agent) -> None:
        """Test that function returns the created agent."""
        mock_get_llm.return_value = MagicMock()
        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        from kube_medic.agents.prometheus_agent import create_prometheus_agent

        result = create_prometheus_agent()

        assert result is mock_agent

    @patch("kube_medic.agents.prometheus_agent.create_agent")
    @patch("kube_medic.agents.prometheus_agent.get_llm")
    def test_uses_shared_llm_instance(self, mock_get_llm, mock_create_agent) -> None:
        """Test that agent uses shared LLM instance from helpers."""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        mock_create_agent.return_value = MagicMock()

        from kube_medic.agents.prometheus_agent import create_prometheus_agent

        # Call twice
        create_prometheus_agent()
        create_prometheus_agent()

        # get_llm should be called each time
        assert mock_get_llm.call_count == 2


class TestPrometheusToolsIntegration:
    """Tests for prometheus tools integration."""

    def test_prometheus_tools_has_expected_count(self) -> None:
        """Test that prometheus_tools has expected number of tools."""
        from kube_medic.tools.prometheus import prometheus_tools

        assert len(prometheus_tools) == 2

    def test_prometheus_tools_have_names(self) -> None:
        """Test that all prometheus tools have proper names."""
        from kube_medic.tools.prometheus import prometheus_tools

        expected_names = [
            "prometheus_query",
            "prometheus_query_range",
        ]

        tool_names = [t.name for t in prometheus_tools]

        for name in expected_names:
            assert name in tool_names
