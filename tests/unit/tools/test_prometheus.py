"""
Tests for Prometheus tools.

Tests:
- Prometheus client singleton
- Prometheus query execution
- Prometheus range queries
- Error handling
- Input schema validation
- PromQL sanitization

Uses mocks to avoid requiring a real Prometheus server.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestSanitizePromql:
    """Tests for _sanitize_promql function."""

    def test_removes_escaped_dots(self) -> None:
        """Test that escaped dots are unescaped."""
        from kube_medic.tools.prometheus import _sanitize_promql

        query = r'up{job="kubernetes\.pods"}'
        result = _sanitize_promql(query)
        assert result == 'up{job="kubernetes.pods"}'

    def test_removes_multiple_escaped_dots(self) -> None:
        """Test that multiple escaped dots are unescaped."""
        from kube_medic.tools.prometheus import _sanitize_promql

        query = r'rate(container\.cpu\.usage\.seconds_total[5m])'
        result = _sanitize_promql(query)
        assert result == 'rate(container.cpu.usage.seconds_total[5m])'

    def test_removes_double_escaped_dots(self) -> None:
        """Test that double-escaped dots (from JSON) are unescaped."""
        from kube_medic.tools.prometheus import _sanitize_promql

        # Double backslash as it might come from JSON parsing
        query = 'up{job="kubernetes\\\\.pods"}'
        result = _sanitize_promql(query)
        assert result == 'up{job="kubernetes.pods"}'

    def test_preserves_normal_query(self) -> None:
        """Test that queries without escapes are unchanged."""
        from kube_medic.tools.prometheus import _sanitize_promql

        query = 'up{job="kubernetes-pods"}'
        result = _sanitize_promql(query)
        assert result == query

    def test_preserves_valid_escapes_in_strings(self) -> None:
        """Test that other escape sequences in label values are preserved."""
        from kube_medic.tools.prometheus import _sanitize_promql

        # PromQL uses double quotes and can have escaped quotes
        query = r'up{job="test\"value"}'
        result = _sanitize_promql(query)
        # Should still have escaped quote but dots would be unescaped
        assert result == r'up{job="test\"value"}'

    def test_handles_standalone_backslash(self) -> None:
        """Test that standalone backslashes not before dots are preserved."""
        from kube_medic.tools.prometheus import _sanitize_promql

        query = r'up{path="C:\\temp"}'
        result = _sanitize_promql(query)
        # Backslash not before dot should be preserved
        assert result == r'up{path="C:\\temp"}'


class TestGetPrometheusClient:
    """Tests for Prometheus client singleton."""

    @patch("kube_medic.tools.prometheus.PrometheusConnect")
    @patch("kube_medic.tools.prometheus.get_settings")
    def test_creates_client_with_settings(self, mock_settings, mock_prom_connect) -> None:
        """Test that client is created with correct settings."""
        import kube_medic.tools.prometheus as prom_module
        prom_module._prom_client = None  # Reset singleton

        mock_settings.return_value = MagicMock(
            prometheus_url="http://prometheus:9090",
            prometheus_username="",
            prometheus_password="",
        )

        from kube_medic.tools.prometheus import get_prometheus_client

        client = get_prometheus_client()

        mock_prom_connect.assert_called_once_with(
            url="http://prometheus:9090",
            headers=None,
            disable_ssl=True,
        )

    @patch("kube_medic.tools.prometheus.PrometheusConnect")
    @patch("kube_medic.tools.prometheus.get_settings")
    def test_creates_client_with_basic_auth(self, mock_settings, mock_prom_connect) -> None:
        """Test that client is created with basic auth headers when credentials are provided."""
        import kube_medic.tools.prometheus as prom_module
        prom_module._prom_client = None  # Reset singleton

        mock_settings.return_value = MagicMock(
            prometheus_url="http://prometheus:9090",
            prometheus_username="admin",
            prometheus_password="secret123",
        )

        from kube_medic.tools.prometheus import get_prometheus_client

        client = get_prometheus_client()

        # Verify PrometheusConnect was called with auth header
        call_args = mock_prom_connect.call_args
        assert call_args.kwargs["url"] == "http://prometheus:9090"
        assert call_args.kwargs["disable_ssl"] is True
        assert "headers" in call_args.kwargs
        assert "Authorization" in call_args.kwargs["headers"]
        # Base64 of "admin:secret123" is "YWRtaW46c2VjcmV0MTIz"
        assert call_args.kwargs["headers"]["Authorization"] == "Basic YWRtaW46c2VjcmV0MTIz"

    @patch("kube_medic.tools.prometheus.PrometheusConnect")
    @patch("kube_medic.tools.prometheus.get_settings")
    def test_creates_client_without_auth_when_only_username(self, mock_settings, mock_prom_connect) -> None:
        """Test that client is created without auth when only username is provided."""
        import kube_medic.tools.prometheus as prom_module
        prom_module._prom_client = None  # Reset singleton

        mock_settings.return_value = MagicMock(
            prometheus_url="http://prometheus:9090",
            prometheus_username="admin",
            prometheus_password="",
        )

        from kube_medic.tools.prometheus import get_prometheus_client

        client = get_prometheus_client()

        mock_prom_connect.assert_called_once_with(
            url="http://prometheus:9090",
            headers=None,
            disable_ssl=True,
        )

    @patch("kube_medic.tools.prometheus.PrometheusConnect")
    @patch("kube_medic.tools.prometheus.get_settings")
    def test_returns_singleton(self, mock_settings, mock_prom_connect) -> None:
        """Test that same client instance is returned on subsequent calls."""
        import kube_medic.tools.prometheus as prom_module
        prom_module._prom_client = None  # Reset singleton

        mock_settings.return_value = MagicMock(
            prometheus_url="http://prometheus:9090",
            prometheus_username="",
            prometheus_password="",
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

    @patch("kube_medic.tools.prometheus.query_prometheus")
    @patch("kube_medic.tools.prometheus.get_settings")
    def test_formats_metric_without_name(self, mock_settings, mock_query) -> None:
        """Test formatting when metric has no __name__ field."""
        mock_settings.return_value = MagicMock(prometheus_max_series_results=20)
        mock_query.return_value = {
            "status": "success",
            "data": {
                "result": [
                    {
                        "metric": {"instance": "localhost:9090"},
                        "value": [1234567890, "42"]
                    }
                ]
            }
        }

        from kube_medic.tools.prometheus import prometheus_query

        result = prometheus_query.invoke({"query": "some_query"})

        assert "unknown" in result
        assert 'instance="localhost:9090"' in result

    @patch("kube_medic.tools.prometheus.query_prometheus")
    @patch("kube_medic.tools.prometheus.get_settings")
    def test_formats_metric_with_no_labels(self, mock_settings, mock_query) -> None:
        """Test formatting when metric has only __name__ and no other labels."""
        mock_settings.return_value = MagicMock(prometheus_max_series_results=20)
        mock_query.return_value = {
            "status": "success",
            "data": {
                "result": [
                    {
                        "metric": {"__name__": "simple_metric"},
                        "value": [1234567890, "100"]
                    }
                ]
            }
        }

        from kube_medic.tools.prometheus import prometheus_query

        result = prometheus_query.invoke({"query": "simple_metric"})

        assert "simple_metric{}" in result
        assert "100" in result


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

    @patch("kube_medic.tools.prometheus.get_prometheus_client")
    @patch("kube_medic.tools.prometheus.get_settings")
    def test_range_query_respects_max_results_limit(self, mock_settings, mock_get_client) -> None:
        """Test that range query respects max results limit for series."""
        mock_settings.return_value = MagicMock(prometheus_max_series_results=2)

        # Create 10 mock series
        mock_results = [
            {
                "metric": {"__name__": f"metric_{i}", "pod": f"pod-{i}"},
                "values": [[1704067200, str(i)]]
            }
            for i in range(10)
        ]

        mock_client = MagicMock()
        mock_client.custom_query_range.return_value = mock_results
        mock_get_client.return_value = mock_client

        from kube_medic.tools.prometheus import prometheus_query_range

        result = prometheus_query_range.invoke({
            "query": "test_query",
            "start": "1h",
            "end": "now",
            "step": "1m"
        })

        assert "more series" in result
        # Should only show 2 series in output
        assert "metric_0" in result
        assert "metric_1" in result
        # metric_2 and beyond should not be shown
        assert "metric_9" not in result

    @patch("kube_medic.tools.prometheus.get_prometheus_client")
    @patch("kube_medic.tools.prometheus.get_settings")
    def test_range_query_with_empty_values(self, mock_settings, mock_get_client) -> None:
        """Test range query handles series with empty values list."""
        mock_settings.return_value = MagicMock(prometheus_max_series_results=20)

        mock_client = MagicMock()
        mock_client.custom_query_range.return_value = [
            {
                "metric": {"__name__": "empty_metric"},
                "values": []
            }
        ]
        mock_get_client.return_value = mock_client

        from kube_medic.tools.prometheus import prometheus_query_range

        result = prometheus_query_range.invoke({
            "query": "empty_metric",
            "start": "1h",
            "end": "now",
            "step": "1m"
        })

        assert "empty_metric" in result
        assert "Data points: 0" in result
        # Should not crash and should not show first/last/stats

    @patch("kube_medic.tools.prometheus.get_prometheus_client")
    @patch("kube_medic.tools.prometheus.get_settings")
    def test_range_query_shows_first_and_last_values(self, mock_settings, mock_get_client) -> None:
        """Test range query shows first and last timestamp values."""
        mock_settings.return_value = MagicMock(prometheus_max_series_results=20)

        mock_client = MagicMock()
        mock_client.custom_query_range.return_value = [
            {
                "metric": {"__name__": "test_metric"},
                "values": [
                    [1704067200, "100"],  # 2024-01-01 00:00:00
                    [1704067260, "150"],
                    [1704067320, "200"],  # 2024-01-01 00:02:00
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

        assert "First:" in result
        assert "= 100" in result
        assert "Last:" in result
        assert "= 200" in result

    @patch("kube_medic.tools.prometheus.get_prometheus_client")
    @patch("kube_medic.tools.prometheus.get_settings")
    def test_range_query_with_all_nan_values(self, mock_settings, mock_get_client) -> None:
        """Test range query handles series where all values are NaN."""
        mock_settings.return_value = MagicMock(prometheus_max_series_results=20)

        mock_client = MagicMock()
        mock_client.custom_query_range.return_value = [
            {
                "metric": {"__name__": "nan_metric"},
                "values": [
                    [1704067200, "NaN"],
                    [1704067260, "NaN"],
                ]
            }
        ]
        mock_get_client.return_value = mock_client

        from kube_medic.tools.prometheus import prometheus_query_range

        result = prometheus_query_range.invoke({
            "query": "nan_metric",
            "start": "1h",
            "end": "now",
            "step": "1m"
        })

        # Should not crash, should show first/last but no stats
        assert "nan_metric" in result
        assert "Data points: 2" in result
        # Stats should not be shown when all values are NaN
        assert "Min:" not in result


class TestInputSchemas:
    """Tests for Pydantic input schemas."""

    def test_prometheus_query_input_requires_query(self) -> None:
        """Test that PrometheusQueryInput requires a query field."""
        from pydantic import ValidationError
        from kube_medic.tools.prometheus import PrometheusQueryInput

        with pytest.raises(ValidationError):
            PrometheusQueryInput()

        # Valid input should work
        schema = PrometheusQueryInput(query="up")
        assert schema.query == "up"

    def test_prometheus_range_query_input_defaults(self) -> None:
        """Test that PrometheusRangeQueryInput has correct defaults."""
        from kube_medic.tools.prometheus import PrometheusRangeQueryInput

        schema = PrometheusRangeQueryInput(query="cpu_usage")

        assert schema.query == "cpu_usage"
        assert schema.start == "1h"
        assert schema.end == "now"
        assert schema.step == "1m"

    def test_prometheus_range_query_input_custom_values(self) -> None:
        """Test PrometheusRangeQueryInput with custom values."""
        from kube_medic.tools.prometheus import PrometheusRangeQueryInput

        schema = PrometheusRangeQueryInput(
            query="memory_usage",
            start="24h",
            end="2024-01-01T12:00:00",
            step="5m"
        )

        assert schema.query == "memory_usage"
        assert schema.start == "24h"
        assert schema.end == "2024-01-01T12:00:00"
        assert schema.step == "5m"


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

    def test_tools_have_descriptions(self) -> None:
        """Test that all tools have proper descriptions."""
        from kube_medic.tools.prometheus import prometheus_tools

        for tool in prometheus_tools:
            assert tool.description is not None
            assert len(tool.description) > 0
