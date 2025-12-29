"""
Tests for Prometheus tools.

Tests:
- Prometheus query execution
- Cluster health check
- Pod metrics
- Pod restart counts
- Error handling

Uses mocks to avoid requiring a real Prometheus server.
"""

from unittest.mock import MagicMock, patch

import pytest


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
    def test_prometheus_query_success(self, mock_query: MagicMock) -> None:
        """Test prometheus_query with successful result."""
        mock_query.return_value = {
            "status": "success",
            "data": {
                "result": [
                    {"metric": {"__name__": "up"}, "value": [0, "1"]},
                ]
            }
        }

        from kube_medic.tools.prometheus import prometheus_query

        result = prometheus_query.invoke({"query": "up"})

        assert "up" in result
        assert "Query:" in result

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

    @patch("kube_medic.tools.prometheus.query_prometheus")
    def test_get_pod_cpu_memory_success(self, mock_query: MagicMock) -> None:
        """Test get_pod_cpu_memory returns metrics."""
        mock_query.side_effect = [
            # CPU response
            {
                "status": "success",
                "data": {
                    "result": [
                        {
                            "metric": {"namespace": "default", "pod": "nginx-1"},
                            "value": [0, "0.5"]
                        }
                    ]
                }
            },
            # Memory response
            {
                "status": "success",
                "data": {
                    "result": [
                        {
                            "metric": {"namespace": "default", "pod": "nginx-1"},
                            "value": [0, "512"]
                        }
                    ]
                }
            }
        ]

        from kube_medic.tools.prometheus import get_pod_cpu_memory

        result = get_pod_cpu_memory.invoke({})

        assert "Found" in result or "default" in result

    @patch("kube_medic.tools.prometheus.query_prometheus")
    def test_get_pod_restarts_success(self, mock_query: MagicMock) -> None:
        """Test get_pod_restarts returns restart info."""
        mock_query.return_value = {
            "status": "success",
            "data": {
                "result": [
                    {
                        "metric": {"namespace": "default", "pod": "crash-loop-pod"},
                        "value": [0, "5"]
                    }
                ]
            }
        }

        from kube_medic.tools.prometheus import get_pod_restarts

        result = get_pod_restarts.invoke({})

        assert "Found" in result or "restart" in result.lower()

    @patch("kube_medic.tools.prometheus.query_prometheus")
    def test_prometheus_max_results_limit(self, mock_query: MagicMock) -> None:
        """Test that prometheus_query respects max results limit."""
        # Create 100 mock results
        mock_results = [
            {"metric": {"__name__": f"metric_{i}"}, "value": [0, "1"]}
            for i in range(100)
        ]

        mock_query.return_value = {
            "status": "success",
            "data": {"result": mock_results}
        }

        from kube_medic.tools.prometheus import prometheus_query

        result = prometheus_query.invoke({"query": "test_query"})

        # Should mention truncation or limiting
        assert "..." in result or "more results" in result

