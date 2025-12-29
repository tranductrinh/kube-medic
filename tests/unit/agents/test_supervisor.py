"""
Tests for Supervisor agent.

Tests:
- AgentQueryInput schema
- run_agent helper function
- Supervisor system prompt
- Supervisor agent creation
- Memory configuration
- Specialist agent delegation
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError


class TestAgentQueryInput:
    """Tests for AgentQueryInput Pydantic model."""

    def test_valid_request(self) -> None:
        """Test that valid request is accepted."""
        from kube_medic.agents.supervisor import AgentQueryInput

        query = AgentQueryInput(request="Check pod status")

        assert query.request == "Check pod status"

    def test_request_is_required(self) -> None:
        """Test that request field is required."""
        from kube_medic.agents.supervisor import AgentQueryInput

        with pytest.raises(ValidationError) as exc_info:
            AgentQueryInput()

        assert "request" in str(exc_info.value)

    def test_empty_request_allowed(self) -> None:
        """Test that empty string is technically allowed (no min length)."""
        from kube_medic.agents.supervisor import AgentQueryInput

        query = AgentQueryInput(request="")

        assert query.request == ""

    def test_long_request(self) -> None:
        """Test that long requests are accepted."""
        from kube_medic.agents.supervisor import AgentQueryInput

        long_request = "Check the status of " + "pod " * 100
        query = AgentQueryInput(request=long_request)

        assert query.request == long_request

    def test_has_description(self) -> None:
        """Test that request field has description."""
        from kube_medic.agents.supervisor import AgentQueryInput

        schema = AgentQueryInput.model_json_schema()
        assert "description" in schema["properties"]["request"]


class TestRunAgent:
    """Tests for run_agent helper function."""

    def test_extracts_ai_response(self) -> None:
        """Test that run_agent extracts AI response correctly."""
        from kube_medic.agents.supervisor import run_agent

        mock_agent = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "This is the response"
        mock_message.type = "ai"
        mock_message.tool_calls = None

        mock_agent.invoke.return_value = {"messages": [mock_message]}

        result = run_agent(mock_agent, "test request")

        assert result == "This is the response"

    def test_returns_last_ai_message(self) -> None:
        """Test that run_agent returns last AI message with content."""
        from kube_medic.agents.supervisor import run_agent

        mock_agent = MagicMock()

        # First message
        msg1 = MagicMock()
        msg1.content = "First response"
        msg1.type = "ai"
        msg1.tool_calls = None

        # Second message (should be returned)
        msg2 = MagicMock()
        msg2.content = "Final response"
        msg2.type = "ai"
        msg2.tool_calls = None

        mock_agent.invoke.return_value = {"messages": [msg1, msg2]}

        result = run_agent(mock_agent, "test request")

        assert result == "Final response"

    def test_skips_tool_call_messages(self) -> None:
        """Test that run_agent skips messages with only tool calls."""
        from kube_medic.agents.supervisor import run_agent

        mock_agent = MagicMock()

        # Tool call message (should be skipped)
        tool_msg = MagicMock()
        tool_msg.content = ""
        tool_msg.type = "ai"
        tool_msg.tool_calls = [{"name": "some_tool"}]

        # Real response
        ai_msg = MagicMock()
        ai_msg.content = "Real response"
        ai_msg.type = "ai"
        ai_msg.tool_calls = None

        mock_agent.invoke.return_value = {"messages": [ai_msg, tool_msg]}

        result = run_agent(mock_agent, "test request")

        assert result == "Real response"

    def test_returns_default_on_no_response(self) -> None:
        """Test that run_agent returns default message when no response."""
        from kube_medic.agents.supervisor import run_agent

        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"messages": []}

        result = run_agent(mock_agent, "test request")

        assert result == "No response from agent."

    def test_returns_default_on_empty_messages(self) -> None:
        """Test that run_agent handles empty messages list."""
        from kube_medic.agents.supervisor import run_agent

        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"messages": []}

        result = run_agent(mock_agent, "test request")

        assert "No response" in result

    def test_invokes_agent_with_correct_format(self) -> None:
        """Test that run_agent invokes agent with correct message format."""
        from kube_medic.agents.supervisor import run_agent

        mock_agent = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Response"
        mock_message.type = "ai"
        mock_message.tool_calls = None
        mock_agent.invoke.return_value = {"messages": [mock_message]}

        run_agent(mock_agent, "my request")

        mock_agent.invoke.assert_called_once()
        call_args = mock_agent.invoke.call_args[0][0]
        assert "messages" in call_args
        assert call_args["messages"][0]["role"] == "user"
        assert call_args["messages"][0]["content"] == "my request"


class TestSupervisorSystemPrompt:
    """Tests for Supervisor system prompt."""

    def test_prompt_mentions_kubernetes_expert(self) -> None:
        """Test that prompt mentions Kubernetes expert."""
        from kube_medic.agents.supervisor import SUPERVISOR_SYSTEM_PROMPT

        assert "ask_kubernetes_expert" in SUPERVISOR_SYSTEM_PROMPT

    def test_prompt_mentions_prometheus_expert(self) -> None:
        """Test that prompt mentions Prometheus expert."""
        from kube_medic.agents.supervisor import SUPERVISOR_SYSTEM_PROMPT

        assert "ask_prometheus_expert" in SUPERVISOR_SYSTEM_PROMPT

    def test_prompt_describes_workflow(self) -> None:
        """Test that prompt describes the workflow."""
        from kube_medic.agents.supervisor import SUPERVISOR_SYSTEM_PROMPT

        assert "WORKFLOW" in SUPERVISOR_SYSTEM_PROMPT

    def test_prompt_has_guidelines(self) -> None:
        """Test that prompt has guidelines."""
        from kube_medic.agents.supervisor import SUPERVISOR_SYSTEM_PROMPT

        assert "GUIDELINES" in SUPERVISOR_SYSTEM_PROMPT

    def test_prompt_mentions_response_format(self) -> None:
        """Test that prompt mentions response format."""
        from kube_medic.agents.supervisor import SUPERVISOR_SYSTEM_PROMPT

        assert "RESPONSE FORMAT" in SUPERVISOR_SYSTEM_PROMPT

    def test_prompt_warns_against_auto_fix(self) -> None:
        """Test that prompt warns against automatic fixes."""
        from kube_medic.agents.supervisor import SUPERVISOR_SYSTEM_PROMPT

        assert "NEVER try to fix" in SUPERVISOR_SYSTEM_PROMPT

    def test_prompt_mentions_conversation_context(self) -> None:
        """Test that prompt mentions conversation context/memory."""
        from kube_medic.agents.supervisor import SUPERVISOR_SYSTEM_PROMPT

        assert "conversation" in SUPERVISOR_SYSTEM_PROMPT.lower()
        assert "context" in SUPERVISOR_SYSTEM_PROMPT.lower()


class TestCreateSupervisorAgent:
    """Tests for create_supervisor_agent function."""

    @patch("kube_medic.agents.supervisor.InMemorySaver")
    @patch("kube_medic.agents.supervisor.create_agent")
    @patch("kube_medic.agents.supervisor.create_prometheus_agent")
    @patch("kube_medic.agents.supervisor.create_kubernetes_agent")
    @patch("kube_medic.agents.supervisor.get_llm")
    def test_creates_specialist_agents(
            self,
            mock_get_llm,
            mock_create_k8s,
            mock_create_prom,
            mock_create_agent,
            mock_saver,
    ) -> None:
        """Test that supervisor creates specialist agents."""
        mock_get_llm.return_value = MagicMock()
        mock_create_k8s.return_value = MagicMock()
        mock_create_prom.return_value = MagicMock()
        mock_create_agent.return_value = MagicMock()

        from kube_medic.agents.supervisor import create_supervisor_agent

        create_supervisor_agent()

        mock_create_k8s.assert_called_once()
        mock_create_prom.assert_called_once()

    @patch("kube_medic.agents.supervisor.InMemorySaver")
    @patch("kube_medic.agents.supervisor.create_agent")
    @patch("kube_medic.agents.supervisor.create_prometheus_agent")
    @patch("kube_medic.agents.supervisor.create_kubernetes_agent")
    @patch("kube_medic.agents.supervisor.get_llm")
    def test_creates_with_memory_by_default(
            self,
            mock_get_llm,
            mock_create_k8s,
            mock_create_prom,
            mock_create_agent,
            mock_saver,
    ) -> None:
        """Test that memory is enabled by default."""
        mock_get_llm.return_value = MagicMock()
        mock_create_k8s.return_value = MagicMock()
        mock_create_prom.return_value = MagicMock()
        mock_create_agent.return_value = MagicMock()
        mock_checkpointer = MagicMock()
        mock_saver.return_value = mock_checkpointer

        from kube_medic.agents.supervisor import create_supervisor_agent

        create_supervisor_agent()

        mock_saver.assert_called_once()
        # Verify checkpointer is passed to create_agent
        call_kwargs = mock_create_agent.call_args[1]
        assert call_kwargs["checkpointer"] is mock_checkpointer

    @patch("kube_medic.agents.supervisor.InMemorySaver")
    @patch("kube_medic.agents.supervisor.create_agent")
    @patch("kube_medic.agents.supervisor.create_prometheus_agent")
    @patch("kube_medic.agents.supervisor.create_kubernetes_agent")
    @patch("kube_medic.agents.supervisor.get_llm")
    def test_creates_without_memory_when_disabled(
            self,
            mock_get_llm,
            mock_create_k8s,
            mock_create_prom,
            mock_create_agent,
            mock_saver,
    ) -> None:
        """Test that memory can be disabled."""
        mock_get_llm.return_value = MagicMock()
        mock_create_k8s.return_value = MagicMock()
        mock_create_prom.return_value = MagicMock()
        mock_create_agent.return_value = MagicMock()

        from kube_medic.agents.supervisor import create_supervisor_agent

        create_supervisor_agent(use_memory=False)

        mock_saver.assert_not_called()
        # Verify checkpointer is None
        call_kwargs = mock_create_agent.call_args[1]
        assert call_kwargs["checkpointer"] is None

    @patch("kube_medic.agents.supervisor.InMemorySaver")
    @patch("kube_medic.agents.supervisor.create_agent")
    @patch("kube_medic.agents.supervisor.create_prometheus_agent")
    @patch("kube_medic.agents.supervisor.create_kubernetes_agent")
    @patch("kube_medic.agents.supervisor.get_llm")
    def test_creates_agent_with_llm(
            self,
            mock_get_llm,
            mock_create_k8s,
            mock_create_prom,
            mock_create_agent,
            mock_saver,
    ) -> None:
        """Test that supervisor is created with LLM."""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        mock_create_k8s.return_value = MagicMock()
        mock_create_prom.return_value = MagicMock()
        mock_create_agent.return_value = MagicMock()

        from kube_medic.agents.supervisor import create_supervisor_agent

        create_supervisor_agent()

        call_kwargs = mock_create_agent.call_args[1]
        assert call_kwargs["model"] is mock_llm

    @patch("kube_medic.agents.supervisor.InMemorySaver")
    @patch("kube_medic.agents.supervisor.create_agent")
    @patch("kube_medic.agents.supervisor.create_prometheus_agent")
    @patch("kube_medic.agents.supervisor.create_kubernetes_agent")
    @patch("kube_medic.agents.supervisor.get_llm")
    def test_creates_agent_with_system_prompt(
            self,
            mock_get_llm,
            mock_create_k8s,
            mock_create_prom,
            mock_create_agent,
            mock_saver,
    ) -> None:
        """Test that supervisor is created with system prompt."""
        mock_get_llm.return_value = MagicMock()
        mock_create_k8s.return_value = MagicMock()
        mock_create_prom.return_value = MagicMock()
        mock_create_agent.return_value = MagicMock()

        from kube_medic.agents.supervisor import (
            create_supervisor_agent,
            SUPERVISOR_SYSTEM_PROMPT,
        )

        create_supervisor_agent()

        call_kwargs = mock_create_agent.call_args[1]
        assert call_kwargs["system_prompt"] == SUPERVISOR_SYSTEM_PROMPT

    @patch("kube_medic.agents.supervisor.InMemorySaver")
    @patch("kube_medic.agents.supervisor.create_agent")
    @patch("kube_medic.agents.supervisor.create_prometheus_agent")
    @patch("kube_medic.agents.supervisor.create_kubernetes_agent")
    @patch("kube_medic.agents.supervisor.get_llm")
    def test_creates_agent_with_two_tools(
            self,
            mock_get_llm,
            mock_create_k8s,
            mock_create_prom,
            mock_create_agent,
            mock_saver,
    ) -> None:
        """Test that supervisor is created with exactly two agent tools."""
        mock_get_llm.return_value = MagicMock()
        mock_create_k8s.return_value = MagicMock()
        mock_create_prom.return_value = MagicMock()
        mock_create_agent.return_value = MagicMock()

        from kube_medic.agents.supervisor import create_supervisor_agent

        create_supervisor_agent()

        call_kwargs = mock_create_agent.call_args[1]
        tools = call_kwargs["tools"]
        assert len(tools) == 2

    @patch("kube_medic.agents.supervisor.InMemorySaver")
    @patch("kube_medic.agents.supervisor.create_agent")
    @patch("kube_medic.agents.supervisor.create_prometheus_agent")
    @patch("kube_medic.agents.supervisor.create_kubernetes_agent")
    @patch("kube_medic.agents.supervisor.get_llm")
    def test_tools_have_correct_names(
            self,
            mock_get_llm,
            mock_create_k8s,
            mock_create_prom,
            mock_create_agent,
            mock_saver,
    ) -> None:
        """Test that supervisor tools have correct names."""
        mock_get_llm.return_value = MagicMock()
        mock_create_k8s.return_value = MagicMock()
        mock_create_prom.return_value = MagicMock()
        mock_create_agent.return_value = MagicMock()

        from kube_medic.agents.supervisor import create_supervisor_agent

        create_supervisor_agent()

        call_kwargs = mock_create_agent.call_args[1]
        tools = call_kwargs["tools"]
        tool_names = [t.name for t in tools]

        assert "ask_kubernetes_expert" in tool_names
        assert "ask_prometheus_expert" in tool_names

    @patch("kube_medic.agents.supervisor.InMemorySaver")
    @patch("kube_medic.agents.supervisor.create_agent")
    @patch("kube_medic.agents.supervisor.create_prometheus_agent")
    @patch("kube_medic.agents.supervisor.create_kubernetes_agent")
    @patch("kube_medic.agents.supervisor.get_llm")
    def test_returns_supervisor_agent(
            self,
            mock_get_llm,
            mock_create_k8s,
            mock_create_prom,
            mock_create_agent,
            mock_saver,
    ) -> None:
        """Test that function returns the supervisor agent."""
        mock_get_llm.return_value = MagicMock()
        mock_create_k8s.return_value = MagicMock()
        mock_create_prom.return_value = MagicMock()
        mock_supervisor = MagicMock()
        mock_create_agent.return_value = mock_supervisor

        from kube_medic.agents.supervisor import create_supervisor_agent

        result = create_supervisor_agent()

        assert result is mock_supervisor


class TestSupervisorToolDelegation:
    """Tests for supervisor tool delegation to specialists."""

    @patch("kube_medic.agents.supervisor.InMemorySaver")
    @patch("kube_medic.agents.supervisor.create_agent")
    @patch("kube_medic.agents.supervisor.create_prometheus_agent")
    @patch("kube_medic.agents.supervisor.create_kubernetes_agent")
    @patch("kube_medic.agents.supervisor.get_llm")
    def test_kubernetes_tool_uses_kubernetes_agent(
            self,
            mock_get_llm,
            mock_create_k8s,
            mock_create_prom,
            mock_create_agent,
            mock_saver,
    ) -> None:
        """Test that ask_kubernetes_expert delegates to kubernetes agent."""
        mock_get_llm.return_value = MagicMock()

        # Create mock kubernetes agent
        mock_k8s_agent = MagicMock()
        mock_k8s_response = MagicMock()
        mock_k8s_response.content = "K8s response"
        mock_k8s_response.type = "ai"
        mock_k8s_response.tool_calls = None
        mock_k8s_agent.invoke.return_value = {"messages": [mock_k8s_response]}
        mock_create_k8s.return_value = mock_k8s_agent

        mock_create_prom.return_value = MagicMock()
        mock_create_agent.return_value = MagicMock()

        from kube_medic.agents.supervisor import create_supervisor_agent

        create_supervisor_agent()

        # Get the ask_kubernetes_expert tool
        call_kwargs = mock_create_agent.call_args[1]
        tools = call_kwargs["tools"]
        k8s_tool = next(t for t in tools if t.name == "ask_kubernetes_expert")

        # Call the tool
        result = k8s_tool.invoke({"request": "check pods"})

        # Verify kubernetes agent was called
        mock_k8s_agent.invoke.assert_called_once()
        assert result == "K8s response"

    @patch("kube_medic.agents.supervisor.InMemorySaver")
    @patch("kube_medic.agents.supervisor.create_agent")
    @patch("kube_medic.agents.supervisor.create_prometheus_agent")
    @patch("kube_medic.agents.supervisor.create_kubernetes_agent")
    @patch("kube_medic.agents.supervisor.get_llm")
    def test_metrics_tool_uses_prometheus_agent(
            self,
            mock_get_llm,
            mock_create_k8s,
            mock_create_prom,
            mock_create_agent,
            mock_saver,
    ) -> None:
        """Test that ask_prometheus_expert delegates to prometheus agent."""
        mock_get_llm.return_value = MagicMock()
        mock_create_k8s.return_value = MagicMock()

        # Create mock prometheus agent
        mock_prom_agent = MagicMock()
        mock_prom_response = MagicMock()
        mock_prom_response.content = "Metrics response"
        mock_prom_response.type = "ai"
        mock_prom_response.tool_calls = None
        mock_prom_agent.invoke.return_value = {"messages": [mock_prom_response]}
        mock_create_prom.return_value = mock_prom_agent

        mock_create_agent.return_value = MagicMock()

        from kube_medic.agents.supervisor import create_supervisor_agent

        create_supervisor_agent()

        # Get the ask_prometheus_expert tool
        call_kwargs = mock_create_agent.call_args[1]
        tools = call_kwargs["tools"]
        prom_tool = next(t for t in tools if t.name == "ask_prometheus_expert")

        # Call the tool
        result = prom_tool.invoke({"request": "check CPU"})

        # Verify prometheus agent was called
        mock_prom_agent.invoke.assert_called_once()
        assert result == "Metrics response"


class TestSupervisorToolSchemas:
    """Tests for supervisor tool schemas."""

    @patch("kube_medic.agents.supervisor.InMemorySaver")
    @patch("kube_medic.agents.supervisor.create_agent")
    @patch("kube_medic.agents.supervisor.create_prometheus_agent")
    @patch("kube_medic.agents.supervisor.create_kubernetes_agent")
    @patch("kube_medic.agents.supervisor.get_llm")
    def test_tools_use_agent_query_input_schema(
            self,
            mock_get_llm,
            mock_create_k8s,
            mock_create_prom,
            mock_create_agent,
            mock_saver,
    ) -> None:
        """Test that tools use AgentQueryInput schema."""
        mock_get_llm.return_value = MagicMock()
        mock_create_k8s.return_value = MagicMock()
        mock_create_prom.return_value = MagicMock()
        mock_create_agent.return_value = MagicMock()

        from kube_medic.agents.supervisor import create_supervisor_agent, AgentQueryInput

        create_supervisor_agent()

        call_kwargs = mock_create_agent.call_args[1]
        tools = call_kwargs["tools"]

        for tool in tools:
            assert tool.args_schema == AgentQueryInput

    @patch("kube_medic.agents.supervisor.InMemorySaver")
    @patch("kube_medic.agents.supervisor.create_agent")
    @patch("kube_medic.agents.supervisor.create_prometheus_agent")
    @patch("kube_medic.agents.supervisor.create_kubernetes_agent")
    @patch("kube_medic.agents.supervisor.get_llm")
    def test_kubernetes_tool_has_description(
            self,
            mock_get_llm,
            mock_create_k8s,
            mock_create_prom,
            mock_create_agent,
            mock_saver,
    ) -> None:
        """Test that kubernetes tool has descriptive docstring."""
        mock_get_llm.return_value = MagicMock()
        mock_create_k8s.return_value = MagicMock()
        mock_create_prom.return_value = MagicMock()
        mock_create_agent.return_value = MagicMock()

        from kube_medic.agents.supervisor import create_supervisor_agent

        create_supervisor_agent()

        call_kwargs = mock_create_agent.call_args[1]
        tools = call_kwargs["tools"]
        k8s_tool = next(t for t in tools if t.name == "ask_kubernetes_expert")

        assert "Kubernetes" in k8s_tool.description
        assert "Pod" in k8s_tool.description or "pod" in k8s_tool.description

    @patch("kube_medic.agents.supervisor.InMemorySaver")
    @patch("kube_medic.agents.supervisor.create_agent")
    @patch("kube_medic.agents.supervisor.create_prometheus_agent")
    @patch("kube_medic.agents.supervisor.create_kubernetes_agent")
    @patch("kube_medic.agents.supervisor.get_llm")
    def test_metrics_tool_has_description(
            self,
            mock_get_llm,
            mock_create_k8s,
            mock_create_prom,
            mock_create_agent,
            mock_saver,
    ) -> None:
        """Test that metrics tool has descriptive docstring."""
        mock_get_llm.return_value = MagicMock()
        mock_create_k8s.return_value = MagicMock()
        mock_create_prom.return_value = MagicMock()
        mock_create_agent.return_value = MagicMock()

        from kube_medic.agents.supervisor import create_supervisor_agent

        create_supervisor_agent()

        call_kwargs = mock_create_agent.call_args[1]
        tools = call_kwargs["tools"]
        prom_tool = next(t for t in tools if t.name == "ask_prometheus_expert")

        assert "Prometheus" in prom_tool.description
        assert "metrics" in prom_tool.description.lower()
