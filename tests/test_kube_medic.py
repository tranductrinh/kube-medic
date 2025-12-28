"""
Unit tests for KubeMedic.

Run with: pytest tests/ -v
"""

import os
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# CONFIG TESTS
# =============================================================================

class TestConfig:
    """Tests for configuration module."""

    def test_settings_loads_from_env(self) -> None:
        """Test that settings load from environment variables."""
        # Clear the cache first
        from kube_medic.config import get_settings
        get_settings.cache_clear()

        with patch.dict(os.environ, {
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
            "PROMETHEUS_URL": "http://prometheus:9090",
        }):
            # Clear cache again inside the patch
            get_settings.cache_clear()
            settings = get_settings()

            assert settings.azure_openai_endpoint == "https://test.openai.azure.com"
            assert settings.azure_openai_api_key == "test-key"
            assert settings.azure_openai_deployment_name == "gpt-4o"
            assert settings.prometheus_url == "http://prometheus:9090"

    def test_settings_removes_trailing_slash(self) -> None:
        """Test that URLs have trailing slashes removed."""
        from kube_medic.config import get_settings
        get_settings.cache_clear()

        with patch.dict(os.environ, {
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
            "PROMETHEUS_URL": "http://prometheus:9090/",
        }):
            get_settings.cache_clear()
            settings = get_settings()

            # Trailing slashes should be removed
            assert settings.azure_openai_endpoint == "https://test.openai.azure.com"
            assert settings.prometheus_url == "http://prometheus:9090"

    def test_settings_missing_required_field(self) -> None:
        """Test that missing required fields raise an error."""
        from pydantic import ValidationError
        from kube_medic.config import Settings

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                Settings(
                    _env_file=None,
                    azure_openai_endpoint="https://test.openai.azure.com",
                    azure_openai_api_key="test-key",
                    azure_openai_deployment_name="gpt-4o",
                )

            assert "prometheus_url" in str(exc_info.value)

# =============================================================================
# HELPER TESTS
# =============================================================================

class TestHelpers:
    """Tests for helper functions."""

    def test_format_error(self) -> None:
        """Test that format_error formats exceptions correctly."""
        from kube_medic.utils.helpers import format_error

        error = ValueError("Something went wrong")
        result = format_error(error)

        assert "ValueError" in result
        assert "Something went wrong" in result
        assert "❌" in result

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


# =============================================================================
# KUBERNETES TOOLS TESTS (Mocked)
# =============================================================================

class TestKubernetesTools:
    """Tests for Kubernetes tools (using mocks)."""

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_list_namespaces_success(self, mock_get_client: MagicMock) -> None:
        """Test list_namespaces returns formatted output."""
        # Create mock namespace
        mock_ns = MagicMock()
        mock_ns.metadata.name = "default"
        mock_ns.status.phase = "Active"

        # Create mock client
        mock_client = MagicMock()
        mock_client.list_namespace.return_value.items = [mock_ns]
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import list_namespaces

        result = list_namespaces.invoke({})

        assert "Found 1 namespaces" in result
        assert "default" in result
        assert "Active" in result

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_list_namespaces_empty(self, mock_get_client: MagicMock) -> None:
        """Test list_namespaces handles empty cluster."""
        mock_client = MagicMock()
        mock_client.list_namespace.return_value.items = []
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import list_namespaces

        result = list_namespaces.invoke({})

        assert "No namespaces found" in result

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_list_pods_empty(self, mock_get_client: MagicMock) -> None:
        """Test list_pods handles no pods."""
        mock_client = MagicMock()
        mock_client.list_pod_for_all_namespaces.return_value.items = []
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import list_pods

        result = list_pods.invoke({"namespace": "", "label_selector": ""})

        assert "No pods found" in result

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_get_pod_details_not_found(self, mock_get_client: MagicMock) -> None:
        """Test get_pod_details handles 404."""
        from kubernetes.client.exceptions import ApiException

        mock_client = MagicMock()
        mock_client.read_namespaced_pod.side_effect = ApiException(status=404)
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import get_pod_details

        result = get_pod_details.invoke({
            "pod_name": "nonexistent",
            "namespace": "default"
        })

        assert "not found" in result


# =============================================================================
# PROMETHEUS TOOLS TESTS (Mocked)
# =============================================================================

class TestPrometheusTools:
    """Tests for Prometheus tools (using mocks)."""

    @patch("kube_medic.tools.prometheus.query_prometheus")
    def test_get_cluster_health_success(self, mock_query: MagicMock) -> None:
        """Test get_cluster_health formats output correctly."""
        # Mock Prometheus response
        mock_query.return_value = {
            "status": "success",
            "data": {
                "result": [
                    {"metric": {"phase": "Running"}, "value": [0, "10"]},
                    {"metric": {"phase": "Pending"}, "value": [0, "2"]},
                ]
            }
        }

        from kube_medic.tools.prometheus import get_cluster_health

        result = get_cluster_health.invoke({})

        assert "Cluster Health" in result
        assert "Running" in result

    @patch("kube_medic.tools.prometheus.query_prometheus")
    def test_prometheus_query_error(self, mock_query: MagicMock) -> None:
        """Test prometheus_query handles errors."""
        mock_query.return_value = {
            "status": "error",
            "error": "connection refused"
        }

        from kube_medic.tools.prometheus import prometheus_query

        result = prometheus_query.invoke({"query": "up"})

        assert "error" in result.lower()

    @patch("kube_medic.tools.prometheus.query_prometheus")
    def test_prometheus_query_no_data(self, mock_query: MagicMock) -> None:
        """Test prometheus_query handles empty results."""
        mock_query.return_value = {
            "status": "success",
            "data": {"result": []}
        }

        from kube_medic.tools.prometheus import prometheus_query

        result = prometheus_query.invoke({"query": "nonexistent_metric"})

        assert "No data" in result


# =============================================================================
# INTEGRATION MARKER (Skip by default)
# =============================================================================

@pytest.mark.integration
class TestIntegration:
    """
    Integration tests requiring live cluster.

    Run with: pytest tests/ -v -m integration
    Skip with: pytest tests/ -v -m "not integration"
    """

    @pytest.fixture(autouse=True)
    def skip_if_no_env(self) -> None:
        """Skip if .env is not configured."""
        if not os.environ.get("PROMETHEUS_URL"):
            pytest.skip("PROMETHEUS_URL not set - skipping integration test")

    def test_config_loads(self) -> None:
        """Test that config loads from real .env."""
        from kube_medic.config import get_settings

        settings = get_settings()
        assert settings.prometheus_url is not None
