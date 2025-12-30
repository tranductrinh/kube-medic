"""
Integration tests requiring live services.

Tests that validate real interactions with:
- Kubernetes cluster
- Prometheus server
- Azure OpenAI API

Run with: pytest tests/ -v -m integration
Skip with: pytest tests/ -v -m "not integration"
"""

import os

import pytest


@pytest.mark.integration
class TestIntegrationConfig:
    """Integration tests for configuration with real .env."""

    @pytest.fixture(autouse=True)
    def skip_if_no_env(self) -> None:
        """Skip if .env is not configured with required vars."""
        required_vars = [
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_DEPLOYMENT_NAME",
            "PROMETHEUS_URL",
        ]
        missing = [v for v in required_vars if not os.environ.get(v)]
        if missing:
            pytest.skip(f"Missing env vars: {', '.join(missing)}")

    def test_config_loads_from_env_file(self) -> None:
        """Test that config loads from real .env file."""
        from kube_medic.config import get_settings

        settings = get_settings()
        assert settings.azure_openai_endpoint is not None
        assert settings.azure_openai_api_key is not None
        assert settings.azure_openai_deployment_name is not None
        assert settings.prometheus_url is not None

    def test_config_has_valid_values(self) -> None:
        """Test that loaded config has valid values."""
        from kube_medic.config import get_settings

        settings = get_settings()

        # Validate types
        assert isinstance(settings.azure_openai_endpoint, str)
        assert isinstance(settings.prometheus_url, str)
        assert isinstance(settings.llm_temperature, float)
        assert isinstance(settings.llm_max_tokens, int)

        # Validate ranges
        assert 0.0 <= settings.llm_temperature <= 2.0
        assert settings.llm_max_tokens > 0
        assert settings.prometheus_timeout > 0

    def test_logging_setup_with_env_vars(self) -> None:
        """Test that logging can be configured via env vars."""
        from kube_medic.logging_config import _get_config_from_env
        import logging

        from unittest.mock import patch

        with patch.dict(os.environ, {
            "LOG_LEVEL": "DEBUG",
            "LOG_FILE": "/tmp/test.log",
        }):
            level, log_file, format_style = _get_config_from_env()

            assert level == logging.DEBUG
            assert log_file == "/tmp/test.log"


@pytest.mark.integration
class TestIntegrationKubernetes:
    """Integration tests for Kubernetes tools (requires real cluster)."""

    @pytest.fixture(autouse=True)
    def skip_if_no_cluster(self) -> None:
        """Skip if Kubernetes cluster is not accessible."""
        try:
            from kube_medic.tools.kubernetes import get_k8s_client
            get_k8s_client()
        except Exception:
            pytest.skip("Kubernetes cluster not accessible")

    def test_k8s_client_initialization(self) -> None:
        """Test that K8s client can be initialized."""
        from kube_medic.tools.kubernetes import get_k8s_client

        client = get_k8s_client()
        assert client is not None

    def test_list_namespaces_returns_results(self) -> None:
        """Test that list_namespaces returns valid results."""
        from kube_medic.tools.kubernetes import list_namespaces

        result = list_namespaces.invoke({})

        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain namespace names
        assert "namespace" in result.lower() or "Found" in result

    def test_list_pods_no_error(self) -> None:
        """Test that list_pods doesn't raise errors."""
        from kube_medic.tools.kubernetes import list_pods

        result = list_pods.invoke({"namespace": "", "label_selector": ""})

        assert isinstance(result, str)
        assert len(result) > 0

    def test_k8s_client_singleton(self) -> None:
        """Test that K8s client uses singleton pattern."""
        from kube_medic.tools.kubernetes import get_k8s_client

        client1 = get_k8s_client()
        client2 = get_k8s_client()

        # Should be the same instance
        assert client1 is client2


@pytest.mark.integration
class TestIntegrationPrometheus:
    """Integration tests for Prometheus tools (requires real Prometheus)."""

    @pytest.fixture(autouse=True)
    def skip_if_no_prometheus(self) -> None:
        """Skip if Prometheus is not accessible."""
        try:
            from kube_medic.config import get_settings
            from kube_medic.tools.prometheus import query_prometheus

            settings = get_settings()
            response = query_prometheus("up")
            if response.get("status") == "error":
                pytest.skip("Prometheus not accessible")
        except Exception:
            pytest.skip("Prometheus not accessible")

    def test_prometheus_query_basic(self) -> None:
        """Test that basic Prometheus query works."""
        from kube_medic.tools.prometheus import query_prometheus

        result = query_prometheus("up")

        # Should be a dict with status
        assert isinstance(result, dict)
        assert "status" in result

    def test_prometheus_query_error_handling(self) -> None:
        """Test that Prometheus handles invalid queries gracefully."""
        from kube_medic.tools.prometheus import query_prometheus

        # Invalid PromQL should either error or return no results
        result = query_prometheus("invalid_metric_name_xyz_123_abc")

        assert isinstance(result, dict)
        # Should handle gracefully


@pytest.mark.integration
class TestIntegrationAgentCreation:
    """Integration tests for agent creation (requires Azure OpenAI + cluster)."""

    @pytest.fixture(autouse=True)
    def skip_if_incomplete_env(self) -> None:
        """Skip if environment is not fully configured."""
        required = ["AZURE_OPENAI_ENDPOINT", "PROMETHEUS_URL"]
        if not all(os.environ.get(v) for v in required):
            pytest.skip("Incomplete environment configuration")

    def test_specialist_agents_creation(self) -> None:
        """Test that specialist agents can be created."""
        from kube_medic.agents.kubernetes_agent import create_kubernetes_agent
        from kube_medic.agents.prometheus_agent import create_prometheus_agent

        k8s_agent = create_kubernetes_agent()
        prometheus_agent = create_prometheus_agent()

        assert k8s_agent is not None
        assert prometheus_agent is not None

    def test_supervisor_agent_creation(self) -> None:
        """Test that supervisor agent can be created."""
        from kube_medic.agents import create_supervisor_agent

        agent = create_supervisor_agent(use_memory=True)

        assert agent is not None

    def test_llm_instance_singleton(self) -> None:
        """Test that LLM instance uses singleton pattern."""
        from kube_medic.utils.helpers import get_llm

        llm1 = get_llm()
        llm2 = get_llm()

        # Should be the same instance
        assert llm1 is llm2

