"""
Tests for Kubernetes tools.

Tests:
- List namespaces
- List pods
- Get pod details
- Get pod logs
- Get events

Uses mocks to avoid requiring a real Kubernetes cluster.
"""

from unittest.mock import MagicMock, patch

import pytest


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
    def test_list_namespaces_multiple(self, mock_get_client: MagicMock) -> None:
        """Test list_namespaces with multiple namespaces."""
        # Create mock namespaces
        namespaces = []
        for i, name in enumerate(["default", "kube-system", "monitoring"]):
            mock_ns = MagicMock()
            mock_ns.metadata.name = name
            mock_ns.status.phase = "Active"
            namespaces.append(mock_ns)

        mock_client = MagicMock()
        mock_client.list_namespace.return_value.items = namespaces
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import list_namespaces

        result = list_namespaces.invoke({})

        assert "Found 3 namespaces" in result
        assert "default" in result
        assert "kube-system" in result
        assert "monitoring" in result

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
    def test_list_pods_with_namespace_filter(self, mock_get_client: MagicMock) -> None:
        """Test list_pods with namespace filter."""
        mock_client = MagicMock()
        mock_client.list_namespaced_pod.return_value.items = []
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import list_pods

        result = list_pods.invoke({"namespace": "default", "label_selector": ""})

        # Verify it called the correct method
        mock_client.list_namespaced_pod.assert_called_once()

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

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_get_pod_logs_success(self, mock_get_client: MagicMock) -> None:
        """Test get_pod_logs returns logs."""
        mock_client = MagicMock()
        mock_client.read_namespaced_pod_log.return_value = "Log line 1\nLog line 2"
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import get_pod_logs

        result = get_pod_logs.invoke({
            "pod_name": "test-pod",
            "namespace": "default"
        })

        assert "Log line 1" in result
        assert "Log line 2" in result

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_get_pod_logs_empty(self, mock_get_client: MagicMock) -> None:
        """Test get_pod_logs handles empty logs."""
        mock_client = MagicMock()
        mock_client.read_namespaced_pod_log.return_value = ""
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import get_pod_logs

        result = get_pod_logs.invoke({
            "pod_name": "test-pod",
            "namespace": "default"
        })

        assert "No logs found" in result

