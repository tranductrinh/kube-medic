"""
Tests for Network specialist agent.

Tests:
- System prompt content
- Agent creation
- Tool binding
"""

from unittest.mock import MagicMock, patch


class TestNetworkSystemPrompt:
    """Tests for Network agent system prompt."""

    def test_prompt_mentions_network(self) -> None:
        """Test that system prompt mentions network/connectivity."""
        from kube_medic.agents.network_agent import NETWORK_SYSTEM_PROMPT

        assert "network" in NETWORK_SYSTEM_PROMPT.lower()
        assert "connectivity" in NETWORK_SYSTEM_PROMPT.lower()

    def test_prompt_mentions_all_tools(self) -> None:
        """Test that system prompt mentions all available tools."""
        from kube_medic.agents.network_agent import NETWORK_SYSTEM_PROMPT

        expected_tools = [
            "http_check",
        ]

        for tool in expected_tools:
            assert tool in NETWORK_SYSTEM_PROMPT, f"Tool {tool} not in prompt"

    def test_prompt_has_important_instruction(self) -> None:
        """Test that prompt has IMPORTANT instruction for supervisor."""
        from kube_medic.agents.network_agent import NETWORK_SYSTEM_PROMPT

        assert "IMPORTANT" in NETWORK_SYSTEM_PROMPT
        assert "supervisor" in NETWORK_SYSTEM_PROMPT.lower()

    def test_prompt_describes_agent_role(self) -> None:
        """Test that prompt describes the agent's role."""
        from kube_medic.agents.network_agent import NETWORK_SYSTEM_PROMPT

        assert "expert" in NETWORK_SYSTEM_PROMPT.lower()

    def test_prompt_mentions_use_cases(self) -> None:
        """Test that prompt mentions use cases."""
        from kube_medic.agents.network_agent import NETWORK_SYSTEM_PROMPT

        assert "ingress" in NETWORK_SYSTEM_PROMPT.lower()
        assert "health" in NETWORK_SYSTEM_PROMPT.lower()


class TestCreateNetworkAgent:
    """Tests for create_network_agent function."""

    @patch("kube_medic.agents.network_agent.create_agent")
    @patch("kube_medic.agents.network_agent.get_llm")
    def test_creates_agent_with_llm(self, mock_get_llm, mock_create_agent) -> None:
        """Test that agent is created with LLM from get_llm()."""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        mock_create_agent.return_value = MagicMock()

        from kube_medic.agents.network_agent import create_network_agent

        create_network_agent()

        mock_get_llm.assert_called_once()
        # Verify LLM is passed to create_agent
        call_kwargs = mock_create_agent.call_args[1]
        assert call_kwargs["model"] is mock_llm

    @patch("kube_medic.agents.network_agent.create_agent")
    @patch("kube_medic.agents.network_agent.get_llm")
    def test_creates_agent_with_network_tools(self, mock_get_llm, mock_create_agent) -> None:
        """Test that agent is created with network_tools."""
        mock_get_llm.return_value = MagicMock()
        mock_create_agent.return_value = MagicMock()

        from kube_medic.agents.network_agent import create_network_agent
        from kube_medic.tools.network import network_tools

        create_network_agent()

        call_kwargs = mock_create_agent.call_args[1]
        assert call_kwargs["tools"] is network_tools

    @patch("kube_medic.agents.network_agent.create_agent")
    @patch("kube_medic.agents.network_agent.get_llm")
    def test_creates_agent_with_system_prompt(self, mock_get_llm, mock_create_agent) -> None:
        """Test that agent is created with correct system prompt."""
        mock_get_llm.return_value = MagicMock()
        mock_create_agent.return_value = MagicMock()

        from kube_medic.agents.network_agent import (
            create_network_agent,
            NETWORK_SYSTEM_PROMPT,
        )

        create_network_agent()

        call_kwargs = mock_create_agent.call_args[1]
        assert call_kwargs["system_prompt"] == NETWORK_SYSTEM_PROMPT

    @patch("kube_medic.agents.network_agent.create_agent")
    @patch("kube_medic.agents.network_agent.get_llm")
    def test_returns_agent(self, mock_get_llm, mock_create_agent) -> None:
        """Test that function returns the created agent."""
        mock_get_llm.return_value = MagicMock()
        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        from kube_medic.agents.network_agent import create_network_agent

        result = create_network_agent()

        assert result is mock_agent


class TestNetworkToolsIntegration:
    """Tests for network tools integration."""

    def test_network_tools_has_expected_count(self) -> None:
        """Test that network_tools has expected number of tools."""
        from kube_medic.tools.network import network_tools

        assert len(network_tools) == 1

    def test_network_tools_have_names(self) -> None:
        """Test that all network tools have proper names."""
        from kube_medic.tools.network import network_tools

        expected_names = ["http_check"]
        tool_names = [t.name for t in network_tools]

        for name in expected_names:
            assert name in tool_names
