"""
Tests for Kubernetes tools.

Tests:
- Kubernetes client singleton
- List namespaces
- List pods
- Get pod details
- Get pod logs
- Get events
- Error handling

Uses mocks to avoid requiring a real Kubernetes cluster.
"""

from unittest.mock import MagicMock, patch

from kubernetes.client.exceptions import ApiException


class TestGetK8sClient:
    """Tests for Kubernetes client singleton."""

    @patch("kube_medic.tools.kubernetes.config")
    @patch("kube_medic.tools.kubernetes.client")
    def test_loads_kubeconfig_first(self, mock_client, mock_config) -> None:
        """Test that kubeconfig is loaded first (local development)."""
        import kube_medic.tools.kubernetes as k8s_module
        k8s_module._v1_client = None  # Reset singleton

        from kube_medic.tools.kubernetes import get_k8s_client

        client = get_k8s_client()

        mock_config.load_kube_config.assert_called_once()
        mock_client.CoreV1Api.assert_called_once()

    @patch("kube_medic.tools.kubernetes.config")
    @patch("kube_medic.tools.kubernetes.client")
    def test_falls_back_to_incluster_config(self, mock_client, mock_config) -> None:
        """Test fallback to in-cluster config when kubeconfig fails."""
        import kube_medic.tools.kubernetes as k8s_module
        k8s_module._v1_client = None  # Reset singleton

        # Make load_kube_config fail
        mock_config.ConfigException = Exception
        mock_config.load_kube_config.side_effect = mock_config.ConfigException("No kubeconfig")

        from kube_medic.tools.kubernetes import get_k8s_client

        get_k8s_client()

        mock_config.load_incluster_config.assert_called_once()

    @patch("kube_medic.tools.kubernetes.config")
    @patch("kube_medic.tools.kubernetes.client")
    def test_returns_singleton(self, mock_client, mock_config) -> None:
        """Test that same client instance is returned on subsequent calls."""
        import kube_medic.tools.kubernetes as k8s_module
        k8s_module._v1_client = None  # Reset singleton

        from kube_medic.tools.kubernetes import get_k8s_client

        client1 = get_k8s_client()
        client2 = get_k8s_client()

        assert client1 is client2
        # CoreV1Api should only be called once
        assert mock_client.CoreV1Api.call_count == 1


class TestListNamespaces:
    """Tests for list_namespaces tool."""

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_returns_formatted_output(self, mock_get_client) -> None:
        """Test list_namespaces returns formatted output."""
        mock_ns = MagicMock()
        mock_ns.metadata.name = "default"
        mock_ns.status.phase = "Active"

        mock_client = MagicMock()
        mock_client.list_namespace.return_value.items = [mock_ns]
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import list_namespaces

        result = list_namespaces.invoke({})

        assert "Found 1 namespaces" in result
        assert "default" in result
        assert "Active" in result

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_handles_empty_cluster(self, mock_get_client) -> None:
        """Test list_namespaces handles empty cluster."""
        mock_client = MagicMock()
        mock_client.list_namespace.return_value.items = []
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import list_namespaces

        result = list_namespaces.invoke({})

        assert "No namespaces found" in result

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_multiple_namespaces(self, mock_get_client) -> None:
        """Test list_namespaces with multiple namespaces."""
        namespaces = []
        for name in ["default", "kube-system", "monitoring"]:
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
    def test_handles_error(self, mock_get_client) -> None:
        """Test list_namespaces handles errors."""
        mock_client = MagicMock()
        mock_client.list_namespace.side_effect = Exception("Connection refused")
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import list_namespaces

        result = list_namespaces.invoke({})

        assert "Error listing namespaces" in result


class TestListPods:
    """Tests for list_pods tool."""

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_handles_no_pods(self, mock_get_client) -> None:
        """Test list_pods handles no pods."""
        mock_client = MagicMock()
        mock_client.list_pod_for_all_namespaces.return_value.items = []
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import list_pods

        result = list_pods.invoke({"namespace": "", "label_selector": ""})

        assert "No pods found" in result

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_with_namespace_filter(self, mock_get_client) -> None:
        """Test list_pods with namespace filter."""
        mock_client = MagicMock()
        mock_client.list_namespaced_pod.return_value.items = []
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import list_pods

        list_pods.invoke({"namespace": "default", "label_selector": ""})

        mock_client.list_namespaced_pod.assert_called_once_with(
            namespace="default",
            label_selector=None
        )

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_with_label_selector(self, mock_get_client) -> None:
        """Test list_pods with label selector."""
        mock_client = MagicMock()
        mock_client.list_pod_for_all_namespaces.return_value.items = []
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import list_pods

        list_pods.invoke({"namespace": "", "label_selector": "app=nginx"})

        mock_client.list_pod_for_all_namespaces.assert_called_once_with(
            label_selector="app=nginx"
        )

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_returns_pod_info(self, mock_get_client) -> None:
        """Test list_pods returns pod information."""
        # Create mock pod
        mock_pod = MagicMock()
        mock_pod.metadata.namespace = "default"
        mock_pod.metadata.name = "nginx-abc123"
        mock_pod.status.phase = "Running"
        mock_pod.status.container_statuses = None

        mock_client = MagicMock()
        mock_client.list_pod_for_all_namespaces.return_value.items = [mock_pod]
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import list_pods

        result = list_pods.invoke({})

        assert "Found 1 pods" in result
        assert "nginx-abc123" in result
        assert "Running" in result

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_shows_restart_count(self, mock_get_client) -> None:
        """Test list_pods shows restart count."""
        mock_container_status = MagicMock()
        mock_container_status.restart_count = 5
        mock_container_status.state.waiting = None
        mock_container_status.state.terminated = None

        mock_pod = MagicMock()
        mock_pod.metadata.namespace = "default"
        mock_pod.metadata.name = "crasher"
        mock_pod.status.phase = "Running"
        mock_pod.status.container_statuses = [mock_container_status]

        mock_client = MagicMock()
        mock_client.list_pod_for_all_namespaces.return_value.items = [mock_pod]
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import list_pods

        result = list_pods.invoke({})

        assert "restarts: 5" in result

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_shows_waiting_status(self, mock_get_client) -> None:
        """Test list_pods shows waiting status reason."""
        mock_container_status = MagicMock()
        mock_container_status.restart_count = 0
        mock_container_status.state.waiting.reason = "ImagePullBackOff"
        mock_container_status.state.terminated = None

        mock_pod = MagicMock()
        mock_pod.metadata.namespace = "default"
        mock_pod.metadata.name = "failing-pod"
        mock_pod.status.phase = "Pending"
        mock_pod.status.container_statuses = [mock_container_status]

        mock_client = MagicMock()
        mock_client.list_pod_for_all_namespaces.return_value.items = [mock_pod]
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import list_pods

        result = list_pods.invoke({})

        assert "ImagePullBackOff" in result

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_handles_error(self, mock_get_client) -> None:
        """Test list_pods handles errors."""
        mock_client = MagicMock()
        mock_client.list_pod_for_all_namespaces.side_effect = Exception("Connection failed")
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import list_pods

        result = list_pods.invoke({})

        assert "Error listing pods" in result


class TestGetPodDetails:
    """Tests for get_pod_details tool."""

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_returns_pod_info(self, mock_get_client) -> None:
        """Test get_pod_details returns pod information."""
        mock_pod = MagicMock()
        mock_pod.status.phase = "Running"
        mock_pod.spec.node_name = "node-1"
        mock_pod.status.pod_ip = "10.0.0.1"
        mock_pod.status.container_statuses = None
        mock_pod.status.conditions = None
        mock_pod.metadata.labels = {"app": "nginx"}

        mock_client = MagicMock()
        mock_client.read_namespaced_pod.return_value = mock_pod
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import get_pod_details

        result = get_pod_details.invoke({
            "pod_name": "nginx-pod",
            "namespace": "default"
        })

        assert "Pod: default/nginx-pod" in result
        assert "Status: Running" in result
        assert "Node: node-1" in result
        assert "IP: 10.0.0.1" in result
        assert "Labels:" in result

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_shows_container_status(self, mock_get_client) -> None:
        """Test get_pod_details shows container status."""
        mock_container_status = MagicMock()
        mock_container_status.name = "nginx"
        mock_container_status.ready = True
        mock_container_status.restart_count = 0
        mock_container_status.state.running = True
        mock_container_status.state.waiting = None
        mock_container_status.state.terminated = None

        mock_pod = MagicMock()
        mock_pod.status.phase = "Running"
        mock_pod.spec.node_name = "node-1"
        mock_pod.status.pod_ip = "10.0.0.1"
        mock_pod.status.container_statuses = [mock_container_status]
        mock_pod.status.conditions = None
        mock_pod.metadata.labels = None

        mock_client = MagicMock()
        mock_client.read_namespaced_pod.return_value = mock_pod
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import get_pod_details

        result = get_pod_details.invoke({
            "pod_name": "nginx-pod",
            "namespace": "default"
        })

        assert "nginx: Running" in result
        assert "Ready: True" in result
        assert "Restarts: 0" in result

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_shows_conditions(self, mock_get_client) -> None:
        """Test get_pod_details shows pod conditions."""
        mock_condition = MagicMock()
        mock_condition.type = "Ready"
        mock_condition.status = "True"
        mock_condition.reason = None

        mock_pod = MagicMock()
        mock_pod.status.phase = "Running"
        mock_pod.spec.node_name = "node-1"
        mock_pod.status.pod_ip = "10.0.0.1"
        mock_pod.status.container_statuses = None
        mock_pod.status.conditions = [mock_condition]
        mock_pod.metadata.labels = None

        mock_client = MagicMock()
        mock_client.read_namespaced_pod.return_value = mock_pod
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import get_pod_details

        result = get_pod_details.invoke({
            "pod_name": "nginx-pod",
            "namespace": "default"
        })

        assert "Conditions:" in result
        assert "Ready: True" in result

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_handles_not_found(self, mock_get_client) -> None:
        """Test get_pod_details handles 404."""
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
    def test_handles_api_error(self, mock_get_client) -> None:
        """Test get_pod_details handles API errors."""
        mock_client = MagicMock()
        mock_client.read_namespaced_pod.side_effect = ApiException(status=500, reason="Server error")
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import get_pod_details

        result = get_pod_details.invoke({
            "pod_name": "test-pod",
            "namespace": "default"
        })

        assert "Error getting pod details" in result


class TestGetPodLogs:
    """Tests for get_pod_logs tool."""

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    @patch("kube_medic.tools.kubernetes.get_settings")
    def test_returns_logs(self, mock_settings, mock_get_client) -> None:
        """Test get_pod_logs returns logs."""
        mock_settings.return_value = MagicMock(
            k8s_logs_tail_lines=100,
            k8s_logs_max_chars=10000
        )

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
    @patch("kube_medic.tools.kubernetes.get_settings")
    def test_handles_empty_logs(self, mock_settings, mock_get_client) -> None:
        """Test get_pod_logs handles empty logs."""
        mock_settings.return_value = MagicMock(
            k8s_logs_tail_lines=100,
            k8s_logs_max_chars=10000
        )

        mock_client = MagicMock()
        mock_client.read_namespaced_pod_log.return_value = ""
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import get_pod_logs

        result = get_pod_logs.invoke({
            "pod_name": "test-pod",
            "namespace": "default"
        })

        assert "No logs found" in result

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    @patch("kube_medic.tools.kubernetes.get_settings")
    def test_with_container_specified(self, mock_settings, mock_get_client) -> None:
        """Test get_pod_logs with container specified."""
        mock_settings.return_value = MagicMock(
            k8s_logs_tail_lines=100,
            k8s_logs_max_chars=10000
        )

        mock_client = MagicMock()
        mock_client.read_namespaced_pod_log.return_value = "Container logs"
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import get_pod_logs

        get_pod_logs.invoke({
            "pod_name": "test-pod",
            "namespace": "default",
            "container": "nginx"
        })

        mock_client.read_namespaced_pod_log.assert_called_once()
        call_kwargs = mock_client.read_namespaced_pod_log.call_args[1]
        assert call_kwargs["container"] == "nginx"

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    @patch("kube_medic.tools.kubernetes.get_settings")
    def test_with_custom_tail_lines(self, mock_settings, mock_get_client) -> None:
        """Test get_pod_logs with custom tail lines."""
        mock_settings.return_value = MagicMock(
            k8s_logs_tail_lines=100,
            k8s_logs_max_chars=10000
        )

        mock_client = MagicMock()
        mock_client.read_namespaced_pod_log.return_value = "Logs"
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import get_pod_logs

        get_pod_logs.invoke({
            "pod_name": "test-pod",
            "namespace": "default",
            "tail_lines": 50
        })

        call_kwargs = mock_client.read_namespaced_pod_log.call_args[1]
        assert call_kwargs["tail_lines"] == 50

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    @patch("kube_medic.tools.kubernetes.get_settings")
    def test_truncates_long_logs(self, mock_settings, mock_get_client) -> None:
        """Test get_pod_logs truncates long logs."""
        mock_settings.return_value = MagicMock(
            k8s_logs_tail_lines=100,
            k8s_logs_max_chars=100  # Short limit for testing
        )

        mock_client = MagicMock()
        mock_client.read_namespaced_pod_log.return_value = "X" * 200
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import get_pod_logs

        result = get_pod_logs.invoke({
            "pod_name": "test-pod",
            "namespace": "default"
        })

        assert "truncated" in result

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    @patch("kube_medic.tools.kubernetes.get_settings")
    def test_handles_not_found(self, mock_settings, mock_get_client) -> None:
        """Test get_pod_logs handles 404."""
        mock_settings.return_value = MagicMock(
            k8s_logs_tail_lines=100,
            k8s_logs_max_chars=10000
        )

        mock_client = MagicMock()
        mock_client.read_namespaced_pod_log.side_effect = ApiException(status=404)
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import get_pod_logs

        result = get_pod_logs.invoke({
            "pod_name": "nonexistent",
            "namespace": "default"
        })

        assert "not found" in result

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    @patch("kube_medic.tools.kubernetes.get_settings")
    def test_handles_api_error(self, mock_settings, mock_get_client) -> None:
        """Test get_pod_logs handles API errors."""
        mock_settings.return_value = MagicMock(
            k8s_logs_tail_lines=100,
            k8s_logs_max_chars=10000
        )

        mock_client = MagicMock()
        mock_client.read_namespaced_pod_log.side_effect = ApiException(
            status=500, reason="Internal error"
        )
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import get_pod_logs

        result = get_pod_logs.invoke({
            "pod_name": "test-pod",
            "namespace": "default"
        })

        assert "Error getting logs" in result


class TestGetEvents:
    """Tests for get_events tool."""

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_returns_events(self, mock_get_client) -> None:
        """Test get_events returns events."""
        mock_event = MagicMock()
        mock_event.type = "Warning"
        mock_event.involved_object.kind = "Pod"
        mock_event.involved_object.name = "test-pod"
        mock_event.reason = "BackOff"
        mock_event.message = "Back-off restarting failed container"
        mock_event.count = 5
        mock_event.last_timestamp = "2024-01-15T10:30:00Z"
        mock_event.event_time = None
        mock_event.metadata.creation_timestamp = "2024-01-15T10:00:00Z"

        mock_client = MagicMock()
        mock_client.list_event_for_all_namespaces.return_value.items = [mock_event]
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import get_events

        result = get_events.invoke({})

        assert "Found 1 events" in result
        assert "Warning" in result
        assert "Pod/test-pod" in result
        assert "BackOff" in result

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_with_namespace_filter(self, mock_get_client) -> None:
        """Test get_events with namespace filter."""
        mock_client = MagicMock()
        mock_client.list_namespaced_event.return_value.items = []
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import get_events

        get_events.invoke({"namespace": "default"})

        mock_client.list_namespaced_event.assert_called_once_with(namespace="default")

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_with_resource_filter(self, mock_get_client) -> None:
        """Test get_events with resource name filter."""
        mock_event1 = MagicMock()
        mock_event1.involved_object.name = "nginx-pod"
        mock_event1.last_timestamp = "2024-01-15T10:30:00Z"
        mock_event1.event_time = None
        mock_event1.metadata.creation_timestamp = "2024-01-15T10:00:00Z"

        mock_event2 = MagicMock()
        mock_event2.involved_object.name = "other-pod"
        mock_event2.last_timestamp = "2024-01-15T10:30:00Z"
        mock_event2.event_time = None
        mock_event2.metadata.creation_timestamp = "2024-01-15T10:00:00Z"

        mock_client = MagicMock()
        mock_client.list_event_for_all_namespaces.return_value.items = [mock_event1, mock_event2]
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import get_events

        result = get_events.invoke({"resource_name": "nginx-pod"})

        assert "nginx-pod" in result
        # other-pod should be filtered out
        assert "other-pod" not in result

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_handles_no_events(self, mock_get_client) -> None:
        """Test get_events handles no events."""
        mock_client = MagicMock()
        mock_client.list_event_for_all_namespaces.return_value.items = []
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import get_events

        result = get_events.invoke({})

        assert "No events found" in result

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_limits_to_20_events(self, mock_get_client) -> None:
        """Test get_events limits to 20 events."""
        # Create 30 mock events
        mock_events = []
        for i in range(30):
            mock_event = MagicMock()
            mock_event.type = "Normal"
            mock_event.involved_object.kind = "Pod"
            mock_event.involved_object.name = f"pod-{i}"
            mock_event.reason = "Scheduled"
            mock_event.message = f"Event {i}"
            mock_event.count = 1
            mock_event.last_timestamp = f"2024-01-15T10:{i:02d}:00Z"
            mock_event.event_time = None
            mock_event.metadata.creation_timestamp = f"2024-01-15T10:00:00Z"
            mock_events.append(mock_event)

        mock_client = MagicMock()
        mock_client.list_event_for_all_namespaces.return_value.items = mock_events
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import get_events

        result = get_events.invoke({})

        # Should only show 20 events
        assert "Found 20 events" in result

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_handles_error(self, mock_get_client) -> None:
        """Test get_events handles errors."""
        mock_client = MagicMock()
        mock_client.list_event_for_all_namespaces.side_effect = Exception("Connection failed")
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import get_events

        result = get_events.invoke({})

        assert "Error getting events" in result


class TestListDeployments:
    """Tests for list_deployments tool."""

    @patch("kube_medic.tools.kubernetes.get_apps_client")
    def test_returns_deployments(self, mock_get_client) -> None:
        """Test list_deployments returns deployment info."""
        mock_dep = MagicMock()
        mock_dep.metadata.namespace = "default"
        mock_dep.metadata.name = "nginx"
        mock_dep.spec.replicas = 3
        mock_dep.status.ready_replicas = 3
        mock_dep.status.available_replicas = 3

        mock_client = MagicMock()
        mock_client.list_deployment_for_all_namespaces.return_value.items = [mock_dep]
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import list_deployments

        result = list_deployments.invoke({})

        assert "Found 1 deployments" in result
        assert "nginx" in result
        assert "3/3 ready" in result

    @patch("kube_medic.tools.kubernetes.get_apps_client")
    def test_handles_no_deployments(self, mock_get_client) -> None:
        """Test list_deployments handles empty result."""
        mock_client = MagicMock()
        mock_client.list_deployment_for_all_namespaces.return_value.items = []
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import list_deployments

        result = list_deployments.invoke({})

        assert "No deployments found" in result

    @patch("kube_medic.tools.kubernetes.get_apps_client")
    def test_with_namespace_filter(self, mock_get_client) -> None:
        """Test list_deployments with namespace filter."""
        mock_client = MagicMock()
        mock_client.list_namespaced_deployment.return_value.items = []
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import list_deployments

        list_deployments.invoke({"namespace": "kube-system"})

        mock_client.list_namespaced_deployment.assert_called_once_with(namespace="kube-system")


class TestListServices:
    """Tests for list_services tool."""

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_returns_services(self, mock_get_client) -> None:
        """Test list_services returns service info."""
        mock_port = MagicMock()
        mock_port.port = 80
        mock_port.protocol = "TCP"

        mock_svc = MagicMock()
        mock_svc.metadata.namespace = "default"
        mock_svc.metadata.name = "nginx-svc"
        mock_svc.spec.type = "ClusterIP"
        mock_svc.spec.cluster_ip = "10.96.0.1"
        mock_svc.spec.ports = [mock_port]

        mock_client = MagicMock()
        mock_client.list_service_for_all_namespaces.return_value.items = [mock_svc]
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import list_services

        result = list_services.invoke({})

        assert "Found 1 services" in result
        assert "nginx-svc" in result
        assert "ClusterIP" in result
        assert "80/TCP" in result

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_handles_no_services(self, mock_get_client) -> None:
        """Test list_services handles empty result."""
        mock_client = MagicMock()
        mock_client.list_service_for_all_namespaces.return_value.items = []
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import list_services

        result = list_services.invoke({})

        assert "No services found" in result


class TestListNodes:
    """Tests for list_nodes tool."""

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_returns_nodes(self, mock_get_client) -> None:
        """Test list_nodes returns node info."""
        mock_condition = MagicMock()
        mock_condition.type = "Ready"
        mock_condition.status = "True"

        mock_node = MagicMock()
        mock_node.metadata.name = "node-1"
        mock_node.metadata.labels = {"node-role.kubernetes.io/control-plane": ""}
        mock_node.status.conditions = [mock_condition]

        mock_client = MagicMock()
        mock_client.list_node.return_value.items = [mock_node]
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import list_nodes

        result = list_nodes.invoke({})

        assert "Found 1 nodes" in result
        assert "node-1" in result
        assert "Ready" in result

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_handles_no_nodes(self, mock_get_client) -> None:
        """Test list_nodes handles empty result."""
        mock_client = MagicMock()
        mock_client.list_node.return_value.items = []
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import list_nodes

        result = list_nodes.invoke({})

        assert "No nodes found" in result


class TestGetNodeDetails:
    """Tests for get_node_details tool."""

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_returns_node_details(self, mock_get_client) -> None:
        """Test get_node_details returns node information."""
        mock_condition = MagicMock()
        mock_condition.type = "Ready"
        mock_condition.status = "True"
        mock_condition.message = "kubelet is posting ready status"

        mock_node = MagicMock()
        mock_node.status.conditions = [mock_condition]
        mock_node.status.capacity = {"cpu": "4", "memory": "8Gi"}
        mock_node.status.allocatable = {"cpu": "3800m", "memory": "7Gi"}
        mock_node.spec.taints = None

        mock_client = MagicMock()
        mock_client.read_node.return_value = mock_node
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import get_node_details

        result = get_node_details.invoke({"node_name": "node-1"})

        assert "Node: node-1" in result
        assert "Ready: True" in result
        assert "Capacity:" in result
        assert "Allocatable:" in result

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_handles_not_found(self, mock_get_client) -> None:
        """Test get_node_details handles 404."""
        mock_client = MagicMock()
        mock_client.read_node.side_effect = ApiException(status=404)
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import get_node_details

        result = get_node_details.invoke({"node_name": "nonexistent"})

        assert "not found" in result


class TestListConfigMaps:
    """Tests for list_configmaps tool."""

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_returns_configmaps(self, mock_get_client) -> None:
        """Test list_configmaps returns ConfigMap info."""
        mock_cm = MagicMock()
        mock_cm.metadata.namespace = "default"
        mock_cm.metadata.name = "app-config"
        mock_cm.data = {"key1": "value1", "key2": "value2"}

        mock_client = MagicMock()
        mock_client.list_config_map_for_all_namespaces.return_value.items = [mock_cm]
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import list_configmaps

        result = list_configmaps.invoke({})

        assert "Found 1 ConfigMaps" in result
        assert "app-config" in result
        assert "2 keys" in result

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_handles_no_configmaps(self, mock_get_client) -> None:
        """Test list_configmaps handles empty result."""
        mock_client = MagicMock()
        mock_client.list_config_map_for_all_namespaces.return_value.items = []
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import list_configmaps

        result = list_configmaps.invoke({})

        assert "No ConfigMaps found" in result


class TestListSecrets:
    """Tests for list_secrets tool."""

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_returns_secrets(self, mock_get_client) -> None:
        """Test list_secrets returns Secret names (not values)."""
        mock_secret = MagicMock()
        mock_secret.metadata.namespace = "default"
        mock_secret.metadata.name = "db-credentials"
        mock_secret.type = "Opaque"
        mock_secret.data = {"username": "xxx", "password": "xxx"}

        mock_client = MagicMock()
        mock_client.list_secret_for_all_namespaces.return_value.items = [mock_secret]
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import list_secrets

        result = list_secrets.invoke({})

        assert "Found 1 Secrets" in result
        assert "db-credentials" in result
        assert "Opaque" in result
        assert "2 keys" in result
        # Should NOT contain actual secret values
        assert "xxx" not in result

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    def test_handles_no_secrets(self, mock_get_client) -> None:
        """Test list_secrets handles empty result."""
        mock_client = MagicMock()
        mock_client.list_secret_for_all_namespaces.return_value.items = []
        mock_get_client.return_value = mock_client

        from kube_medic.tools.kubernetes import list_secrets

        result = list_secrets.invoke({})

        assert "No Secrets found" in result


class TestGetAppsClient:
    """Tests for AppsV1Api client singleton."""

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    @patch("kube_medic.tools.kubernetes.client")
    def test_creates_apps_client(self, mock_client, mock_get_k8s) -> None:
        """Test get_apps_client creates AppsV1Api client."""
        import kube_medic.tools.kubernetes as k8s_module
        k8s_module._apps_client = None  # Reset singleton

        from kube_medic.tools.kubernetes import get_apps_client

        client = get_apps_client()

        mock_client.AppsV1Api.assert_called_once()

    @patch("kube_medic.tools.kubernetes.get_k8s_client")
    @patch("kube_medic.tools.kubernetes.client")
    def test_returns_singleton(self, mock_client, mock_get_k8s) -> None:
        """Test get_apps_client returns singleton."""
        import kube_medic.tools.kubernetes as k8s_module
        k8s_module._apps_client = None  # Reset singleton

        from kube_medic.tools.kubernetes import get_apps_client

        client1 = get_apps_client()
        client2 = get_apps_client()

        assert client1 is client2
        assert mock_client.AppsV1Api.call_count == 1


class TestKubernetesToolsList:
    """Tests for kubernetes_tools list."""

    def test_all_tools_in_list(self) -> None:
        """Test that all kubernetes tools are in the tools list."""
        from kube_medic.tools.kubernetes import (
            kubernetes_tools,
            list_namespaces,
            list_pods,
            get_pod_details,
            get_pod_logs,
            get_events,
            list_deployments,
            list_services,
            list_nodes,
            get_node_details,
            list_configmaps,
            list_secrets,
        )

        assert list_namespaces in kubernetes_tools
        assert list_pods in kubernetes_tools
        assert get_pod_details in kubernetes_tools
        assert get_pod_logs in kubernetes_tools
        assert get_events in kubernetes_tools
        assert list_deployments in kubernetes_tools
        assert list_services in kubernetes_tools
        assert list_nodes in kubernetes_tools
        assert get_node_details in kubernetes_tools
        assert list_configmaps in kubernetes_tools
        assert list_secrets in kubernetes_tools
        assert len(kubernetes_tools) == 11

    def test_tools_have_names(self) -> None:
        """Test that all tools have proper names."""
        from kube_medic.tools.kubernetes import kubernetes_tools

        expected_names = [
            "get_events",
            "get_node_details",
            "get_pod_details",
            "get_pod_logs",
            "list_configmaps",
            "list_deployments",
            "list_namespaces",
            "list_nodes",
            "list_pods",
            "list_secrets",
            "list_services",
        ]

        tool_names = [t.name for t in kubernetes_tools]

        for name in expected_names:
            assert name in tool_names
