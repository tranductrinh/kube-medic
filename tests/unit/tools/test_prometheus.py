"""
Tests for Prometheus tools.

Tests:
- Prometheus client singleton
- Prometheus query execution
- Prometheus range queries
- Error handling

Uses mocks to avoid requiring a real Prometheus server.
"""

from unittest.mock import MagicMock, patch


class TestGetPrometheusClient:
    """Tests for Prometheus client singleton."""

    @patch("kube_medic.tools.prometheus.PrometheusConnect")
    @patch("kube_medic.tools.prometheus.get_settings")
    def test_creates_client_with_settings(self, mock_settings, mock_prom_connect) -> None:
        """Test that client is created with correct settings."""
        import kube_medic.tools.prometheus as prom_module
        prom_module._prom_client = None  # Reset singleton

        mock_settings.return_value = MagicMock(
            prometheus_url="http://prometheus:9090"
        )

        from kube_medic.tools.prometheus import get_prometheus_client

        client = get_prometheus_client()

        mock_prom_connect.assert_called_once_with(
            url="http://prometheus:9090",
            disable_ssl=True,
        )

    @patch("kube_medic.tools.prometheus.PrometheusConnect")
    @patch("kube_medic.tools.prometheus.get_settings")
    def test_returns_singleton(self, mock_settings, mock_prom_connect) -> None:
        """Test that same client instance is returned on subsequent calls."""
        import kube_medic.tools.prometheus as prom_module
        prom_module._prom_client = None  # Reset singleton

        mock_settings.return_value = MagicMock(
            prometheus_url="http://prometheus:9090"
        )

        from kube_medic.tools.prometheus import get_prometheus_client

        client1 = get_prometheus_client()
        client2 = get_prometheus_client()

        assert client1 is client2
        assert mock_prom_connect.call_count == 1


class TestQueryPrometheus:
    """Tests for query_prometheus function."""

    @patch("kube_medic.tools.prometheus.get_prometheus_client")
    def test_successful_query(self, mock_get_client) -> None:
        """Test successful Prometheus query."""
        mock_client = MagicMock()
        mock_client.custom_query.return_value = [
            {"metric": {"__name__": "up"}, "value": [1234567890, "1"]}
        ]
        mock_get_client.return_value = mock_client

        from kube_medic.tools.prometheus import query_prometheus

        result = query_prometheus("up")

        assert result["status"] == "success"
        assert len(result["data"]["result"]) == 1
        mock_client.custom_query.assert_called_once_with(query="up")

    @patch("kube_medic.tools.prometheus.get_prometheus_client")
    def test_query_error(self, mock_get_client) -> None:
        """Test query error handling."""
        mock_client = MagicMock()
        mock_client.custom_query.side_effect = Exception("Connection refused")
        mock_get_client.return_value = mock_client

        from kube_medic.tools.prometheus import query_prometheus

        result = query_prometheus("up")

        assert result["status"] == "error"
        assert "Connection refused" in result["error"]


class TestPrometheusQueryTool:
    """Tests for prometheus_query tool."""

    @patch("kube_medic.tools.prometheus.query_prometheus")
    @patch("kube_medic.tools.prometheus.get_settings")
    def test_formats_results(self, mock_settings, mock_query) -> None:
        """Test that results are formatted correctly."""
        mock_settings.return_value = MagicMock(prometheus_max_series_results=20)
        mock_query.return_value = {
            "status": "success",
            "data": {
                "result": [
                    {
                        "metric": {"__name__": "up", "job": "kubernetes"},
                        "value": [1234567890, "1"]
                    }
                ]
            }
        }

        from kube_medic.tools.prometheus import prometheus_query

        result = prometheus_query.invoke({"query": "up"})

        assert "Query: up" in result
        assert "Results (1 series)" in result
        assert 'job="kubernetes"' in result

    @patch("kube_medic.tools.prometheus.query_prometheus")
    def test_handles_error(self, mock_query) -> None:
        """Test error handling."""
        mock_query.return_value = {
            "status": "error",
            "error": "invalid query"
        }

        from kube_medic.tools.prometheus import prometheus_query

        result = prometheus_query.invoke({"query": "bad{query"})

        assert "Prometheus error" in result
        assert "invalid query" in result

    @patch("kube_medic.tools.prometheus.query_prometheus")
    def test_handles_empty_results(self, mock_query) -> None:
        """Test empty results handling."""
        mock_query.return_value = {
            "status": "success",
            "data": {"result": []}
        }

        from kube_medic.tools.prometheus import prometheus_query

        result = prometheus_query.invoke({"query": "nonexistent_metric"})

        assert "No data returned" in result

    @patch("kube_medic.tools.prometheus.query_prometheus")
    @patch("kube_medic.tools.prometheus.get_settings")
    def test_respects_max_results_limit(self, mock_settings, mock_query) -> None:
        """Test that prometheus_query respects max results limit."""
        mock_settings.return_value = MagicMock(prometheus_max_series_results=5)

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

        assert "more results" in result


class TestPrometheusQueryRangeTool:
    """Tests for prometheus_query_range tool."""

    @patch("kube_medic.tools.prometheus.get_prometheus_client")
    @patch("kube_medic.tools.prometheus.get_settings")
    def test_range_query_success(self, mock_settings, mock_get_client) -> None:
        """Test successful range query."""
        mock_settings.return_value = MagicMock(prometheus_max_series_results=20)

        mock_client = MagicMock()
        mock_client.custom_query_range.return_value = [
            {
                "metric": {"__name__": "cpu_usage", "pod": "test-pod"},
                "values": [
                    [1704067200, "0.5"],
                    [1704067260, "0.6"],
                    [1704067320, "0.7"],
                ]
            }
        ]
        mock_get_client.return_value = mock_client

        from kube_medic.tools.prometheus import prometheus_query_range

        result = prometheus_query_range.invoke({
            "query": "cpu_usage",
            "start": "1h",
            "end": "now",
            "step": "1m"
        })

        assert "Range Query: cpu_usage" in result
        assert "Data points: 3" in result
        assert "Min:" in result
        assert "Max:" in result
        assert "Avg:" in result

    @patch("kube_medic.tools.prometheus.get_prometheus_client")
    @patch("kube_medic.tools.prometheus.get_settings")
    def test_range_query_empty_results(self, mock_settings, mock_get_client) -> None:
        """Test range query with no results."""
        mock_settings.return_value = MagicMock(prometheus_max_series_results=20)

        mock_client = MagicMock()
        mock_client.custom_query_range.return_value = []
        mock_get_client.return_value = mock_client

        from kube_medic.tools.prometheus import prometheus_query_range

        result = prometheus_query_range.invoke({
            "query": "nonexistent",
            "start": "1h",
            "end": "now",
            "step": "1m"
        })

        assert "No data returned" in result

    def test_range_query_invalid_time_format(self) -> None:
        """Test range query with invalid time format."""
        from kube_medic.tools.prometheus import prometheus_query_range

        result = prometheus_query_range.invoke({
            "query": "cpu_usage",
            "start": "invalid",
            "end": "now",
            "step": "1m"
        })

        assert "Invalid time format" in result

    @patch("kube_medic.tools.prometheus.get_prometheus_client")
    @patch("kube_medic.tools.prometheus.get_settings")
    def test_range_query_with_iso_timestamps(self, mock_settings, mock_get_client) -> None:
        """Test range query with ISO timestamp inputs."""
        mock_settings.return_value = MagicMock(prometheus_max_series_results=20)

        mock_client = MagicMock()
        mock_client.custom_query_range.return_value = [
            {
                "metric": {"__name__": "memory"},
                "values": [[1704067200, "100"]]
            }
        ]
        mock_get_client.return_value = mock_client

        from kube_medic.tools.prometheus import prometheus_query_range

        result = prometheus_query_range.invoke({
            "query": "memory",
            "start": "2024-01-01T00:00:00",
            "end": "2024-01-01T01:00:00",
            "step": "5m"
        })

        assert "Range Query: memory" in result
        mock_client.custom_query_range.assert_called_once()

    @patch("kube_medic.tools.prometheus.get_prometheus_client")
    def test_range_query_connection_error(self, mock_get_client) -> None:
        """Test range query handles connection errors."""
        mock_client = MagicMock()
        mock_client.custom_query_range.side_effect = Exception("Connection timeout")
        mock_get_client.return_value = mock_client

        from kube_medic.tools.prometheus import prometheus_query_range

        result = prometheus_query_range.invoke({
            "query": "cpu_usage",
            "start": "1h",
            "end": "now",
            "step": "1m"
        })

        assert "Prometheus error" in result
        assert "Connection timeout" in result

    @patch("kube_medic.tools.prometheus.get_prometheus_client")
    @patch("kube_medic.tools.prometheus.get_settings")
    def test_range_query_calculates_stats(self, mock_settings, mock_get_client) -> None:
        """Test that range query calculates min/max/avg correctly."""
        mock_settings.return_value = MagicMock(prometheus_max_series_results=20)

        mock_client = MagicMock()
        mock_client.custom_query_range.return_value = [
            {
                "metric": {"__name__": "test_metric"},
                "values": [
                    [1704067200, "10"],
                    [1704067260, "20"],
                    [1704067320, "30"],
                ]
            }
        ]
        mock_get_client.return_value = mock_client

        from kube_medic.tools.prometheus import prometheus_query_range

        result = prometheus_query_range.invoke({
            "query": "test_metric",
            "start": "1h",
            "end": "now",
            "step": "1m"
        })

        # Min=10, Max=30, Avg=20
        assert "Min: 10.000" in result
        assert "Max: 30.000" in result
        assert "Avg: 20.000" in result

    @patch("kube_medic.tools.prometheus.get_prometheus_client")
    @patch("kube_medic.tools.prometheus.get_settings")
    def test_range_query_handles_nan_values(self, mock_settings, mock_get_client) -> None:
        """Test that range query handles NaN values in stats calculation."""
        mock_settings.return_value = MagicMock(prometheus_max_series_results=20)

        mock_client = MagicMock()
        mock_client.custom_query_range.return_value = [
            {
                "metric": {"__name__": "test_metric"},
                "values": [
                    [1704067200, "10"],
                    [1704067260, "NaN"],
                    [1704067320, "20"],
                ]
            }
        ]
        mock_get_client.return_value = mock_client

        from kube_medic.tools.prometheus import prometheus_query_range

        result = prometheus_query_range.invoke({
            "query": "test_metric",
            "start": "1h",
            "end": "now",
            "step": "1m"
        })

        # Should calculate stats excluding NaN: Min=10, Max=20, Avg=15
        assert "Min: 10.000" in result
        assert "Max: 20.000" in result
        assert "Avg: 15.000" in result


class TestPrometheusToolsList:
    """Tests for prometheus_tools list."""

    def test_all_tools_in_list(self) -> None:
        """Test that all prometheus tools are in the tools list."""
        from kube_medic.tools.prometheus import (
            prometheus_tools,
            prometheus_query,
            prometheus_query_range,
        )

        assert prometheus_query in prometheus_tools
        assert prometheus_query_range in prometheus_tools
        assert len(prometheus_tools) == 2

    def test_tools_have_names(self) -> None:
        """Test that all tools have proper names."""
        from kube_medic.tools.prometheus import prometheus_tools

        expected_names = [
            "prometheus_query",
            "prometheus_query_range",
        ]

        tool_names = [t.name for t in prometheus_tools]

        for name in expected_names:
            assert name in tool_names
