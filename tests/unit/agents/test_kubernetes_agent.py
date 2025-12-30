"""
Tests for Kubernetes specialist agent.

Tests:
- System prompt content
- Agent creation
- Tool binding
"""

from unittest.mock import MagicMock, patch


class TestKubernetesSystemPrompt:
    """Tests for Kubernetes agent system prompt."""

    def test_prompt_mentions_kubernetes(self) -> None:
        """Test that system prompt mentions Kubernetes."""
        from kube_medic.agents.kubernetes_agent import KUBERNETES_SYSTEM_PROMPT

        assert "Kubernetes" in KUBERNETES_SYSTEM_PROMPT

    def test_prompt_mentions_all_tools(self) -> None:
        """Test that system prompt mentions key tools."""
        from kube_medic.agents.kubernetes_agent import KUBERNETES_SYSTEM_PROMPT

        # Key tools should be mentioned
        assert "list_pods" in KUBERNETES_SYSTEM_PROMPT
        assert "get_pod_logs" in KUBERNETES_SYSTEM_PROMPT
        assert "get_events" in KUBERNETES_SYSTEM_PROMPT

    def test_prompt_has_efficiency_rules(self) -> None:
        """Test that prompt has efficiency rules."""
        from kube_medic.agents.kubernetes_agent import KUBERNETES_SYSTEM_PROMPT

        assert "Efficient rules" in KUBERNETES_SYSTEM_PROMPT

    def test_prompt_describes_agent_role(self) -> None:
        """Test that prompt describes the agent's role."""
        from kube_medic.agents.kubernetes_agent import KUBERNETES_SYSTEM_PROMPT

        assert "expert" in KUBERNETES_SYSTEM_PROMPT.lower()


class TestCreateKubernetesAgent:
    """Tests for create_kubernetes_agent function."""

    @patch("kube_medic.agents.kubernetes_agent.create_agent")
    @patch("kube_medic.agents.kubernetes_agent.get_llm")
    def test_creates_agent_with_llm(self, mock_get_llm, mock_create_agent) -> None:
        """Test that agent is created with LLM from get_llm()."""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        mock_create_agent.return_value = MagicMock()

        from kube_medic.agents.kubernetes_agent import create_kubernetes_agent

        create_kubernetes_agent()

        mock_get_llm.assert_called_once()
        # Verify LLM is passed to create_agent
        call_kwargs = mock_create_agent.call_args[1]
        assert call_kwargs["model"] is mock_llm

    @patch("kube_medic.agents.kubernetes_agent.create_agent")
    @patch("kube_medic.agents.kubernetes_agent.get_llm")
    def test_creates_agent_with_kubernetes_tools(self, mock_get_llm, mock_create_agent) -> None:
        """Test that agent is created with kubernetes_tools."""
        mock_get_llm.return_value = MagicMock()
        mock_create_agent.return_value = MagicMock()

        from kube_medic.agents.kubernetes_agent import (
            create_kubernetes_agent,
        )
        from kube_medic.tools.kubernetes import kubernetes_tools

        create_kubernetes_agent()

        call_kwargs = mock_create_agent.call_args[1]
        assert call_kwargs["tools"] is kubernetes_tools

    @patch("kube_medic.agents.kubernetes_agent.create_agent")
    @patch("kube_medic.agents.kubernetes_agent.get_llm")
    def test_creates_agent_with_system_prompt(self, mock_get_llm, mock_create_agent) -> None:
        """Test that agent is created with correct system prompt."""
        mock_get_llm.return_value = MagicMock()
        mock_create_agent.return_value = MagicMock()

        from kube_medic.agents.kubernetes_agent import (
            create_kubernetes_agent,
            KUBERNETES_SYSTEM_PROMPT,
        )

        create_kubernetes_agent()

        call_kwargs = mock_create_agent.call_args[1]
        assert call_kwargs["system_prompt"] == KUBERNETES_SYSTEM_PROMPT

    @patch("kube_medic.agents.kubernetes_agent.create_agent")
    @patch("kube_medic.agents.kubernetes_agent.get_llm")
    def test_returns_agent(self, mock_get_llm, mock_create_agent) -> None:
        """Test that function returns the created agent."""
        mock_get_llm.return_value = MagicMock()
        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        from kube_medic.agents.kubernetes_agent import create_kubernetes_agent

        result = create_kubernetes_agent()

        assert result is mock_agent

    @patch("kube_medic.agents.kubernetes_agent.create_agent")
    @patch("kube_medic.agents.kubernetes_agent.get_llm")
    def test_uses_shared_llm_instance(self, mock_get_llm, mock_create_agent) -> None:
        """Test that agent uses shared LLM instance from helpers."""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        mock_create_agent.return_value = MagicMock()

        from kube_medic.agents.kubernetes_agent import create_kubernetes_agent

        # Call twice
        create_kubernetes_agent()
        create_kubernetes_agent()

        # get_llm should be called each time (singleton handled by get_llm)
        assert mock_get_llm.call_count == 2


class TestKubernetesToolsIntegration:
    """Tests for kubernetes tools integration."""

    def test_kubernetes_tools_has_expected_count(self) -> None:
        """Test that kubernetes_tools has expected number of tools."""
        from kube_medic.tools.kubernetes import kubernetes_tools

        assert len(kubernetes_tools) == 12

    def test_kubernetes_tools_have_names(self) -> None:
        """Test that all kubernetes tools have proper names."""
        from kube_medic.tools.kubernetes import kubernetes_tools

        expected_names = [
            "get_events",
            "get_node_details",
            "get_pod_details",
            "get_pod_logs",
            "list_configmaps",
            "list_deployments",
            "list_ingresses",
            "list_namespaces",
            "list_nodes",
            "list_pods",
            "list_secrets",
            "list_services",
        ]

        tool_names = [t.name for t in kubernetes_tools]

        for name in expected_names:
            assert name in tool_names
