"""
Unit tests for caching functionality.

Tests that validate:
- Prometheus query caching
- Kubernetes API caching
- Cache statistics and clearing
"""

import pytest
from unittest.mock import patch, MagicMock


class TestPrometheusCaching:
    """Tests for Prometheus query caching."""

    def test_cache_stats_returns_expected_keys(self, sample_config_env):
        """Test that cache stats returns expected structure."""
        from kube_medic.tools.prometheus import get_prometheus_cache_stats

        stats = get_prometheus_cache_stats()

        assert "current_size" in stats
        assert "max_size" in stats
        assert "ttl_seconds" in stats

    def test_clear_cache_returns_count(self, sample_config_env):
        """Test that clearing cache returns count."""
        from kube_medic.tools.prometheus import clear_prometheus_cache

        count = clear_prometheus_cache()
        assert isinstance(count, int)

    @patch('kube_medic.tools.prometheus.get_prometheus_client')
    def test_query_is_cached(self, mock_client, sample_config_env):
        """Test that query results are cached."""
        from kube_medic.tools.prometheus import query_prometheus, clear_prometheus_cache

        # Clear cache first
        clear_prometheus_cache()

        # Set up mock
        mock_prom = MagicMock()
        mock_prom.custom_query.return_value = [{"metric": {}, "value": [0, "1"]}]
        mock_client.return_value = mock_prom

        # First call should hit the API
        result1 = query_prometheus("up")
        assert mock_prom.custom_query.call_count == 1

        # Second call should use cache
        result2 = query_prometheus("up")
        assert mock_prom.custom_query.call_count == 1  # Still 1

        # Results should be the same
        assert result1 == result2


class TestPrometheusQueryValidation:
    """Tests for PromQL query validation."""

    def test_validation_passes_for_simple_query(self, sample_config_env):
        """Test that simple queries pass validation."""
        from kube_medic.tools.prometheus import _validate_promql

        # Should not raise
        _validate_promql("up")
        _validate_promql("rate(http_requests_total[5m])")
        _validate_promql('container_memory_usage_bytes{namespace="default"}')

    def test_validation_fails_for_too_long_query(self, sample_config_env):
        """Test that overly long queries fail validation."""
        from kube_medic.tools.prometheus import _validate_promql, PromQLValidationError

        long_query = "up" + "a" * 2000

        with pytest.raises(PromQLValidationError) as exc_info:
            _validate_promql(long_query)

        assert "maximum length" in str(exc_info.value).lower()

    def test_validation_fails_for_deeply_nested_query(self, sample_config_env):
        """Test that deeply nested queries fail validation."""
        from kube_medic.tools.prometheus import _validate_promql, PromQLValidationError

        # Create a deeply nested query
        nested_query = "sum(" * 15 + "up" + ")" * 15

        with pytest.raises(PromQLValidationError) as exc_info:
            _validate_promql(nested_query)

        assert "nested" in str(exc_info.value).lower()


class TestKubernetesCaching:
    """Tests for Kubernetes API caching."""

    def test_cache_stats_returns_expected_keys(self, sample_config_env):
        """Test that cache stats returns expected structure."""
        from kube_medic.tools.kubernetes import get_k8s_cache_stats

        stats = get_k8s_cache_stats()

        assert "current_size" in stats
        assert "max_size" in stats
        assert "ttl_seconds" in stats

    def test_clear_cache_returns_count(self, sample_config_env):
        """Test that clearing cache returns count."""
        from kube_medic.tools.kubernetes import clear_k8s_cache

        count = clear_k8s_cache()
        assert isinstance(count, int)

    def test_cached_k8s_call_returns_same_result(self, sample_config_env):
        """Test that cached call returns same result."""
        from kube_medic.tools.kubernetes import _cached_k8s_call, clear_k8s_cache

        clear_k8s_cache()

        call_count = 0

        def mock_fn():
            nonlocal call_count
            call_count += 1
            return {"items": [{"name": "test"}]}

        # First call
        result1 = _cached_k8s_call("test_key", mock_fn)
        assert call_count == 1

        # Second call should use cache
        result2 = _cached_k8s_call("test_key", mock_fn)
        assert call_count == 1  # Still 1

        assert result1 == result2

    def test_different_keys_call_function_separately(self, sample_config_env):
        """Test that different cache keys call function separately."""
        from kube_medic.tools.kubernetes import _cached_k8s_call, clear_k8s_cache

        clear_k8s_cache()

        call_count = 0

        def mock_fn():
            nonlocal call_count
            call_count += 1
            return {"count": call_count}

        result1 = _cached_k8s_call("key1", mock_fn)
        result2 = _cached_k8s_call("key2", mock_fn)

        assert call_count == 2
        assert result1 != result2


class TestBoundedMemorySaver:
    """Tests for the bounded memory saver."""

    def test_bounded_memory_saver_creation(self, sample_config_env):
        """Test that bounded memory saver can be created."""
        from kube_medic.agents.supervisor import BoundedMemorySaver

        saver = BoundedMemorySaver(maxsize=100, ttl=60)
        assert saver is not None

    def test_bounded_memory_saver_stats(self, sample_config_env):
        """Test that stats are returned correctly."""
        from kube_medic.agents.supervisor import BoundedMemorySaver

        saver = BoundedMemorySaver(maxsize=100, ttl=60)
        stats = saver.get_stats()

        assert stats["current_size"] == 0
        assert stats["max_size"] == 100
        assert stats["ttl_seconds"] == 60

    def test_bounded_memory_saver_put_and_get(self, sample_config_env):
        """Test that put and get work correctly."""
        from kube_medic.agents.supervisor import BoundedMemorySaver

        saver = BoundedMemorySaver(maxsize=100, ttl=60)

        config = {"configurable": {"thread_id": "test-thread"}}
        checkpoint = {"messages": ["test"]}
        metadata = {"step": 1}
        new_versions = {}

        saver.put(config, checkpoint, metadata, new_versions)

        result = saver.get_tuple(config)
        assert result is not None
        assert result[0] == checkpoint


class TestRecursionMonitoring:
    """Tests for recursion limit monitoring."""

    def test_get_recursion_stats_returns_expected_keys(self, sample_config_env):
        """Test that recursion stats returns expected structure."""
        from kube_medic.utils.helpers import get_recursion_stats

        stats = get_recursion_stats()

        assert "total_hits" in stats
        assert "total_invocations" in stats
        assert "hit_rate_percent" in stats
        assert "by_thread" in stats

    def test_record_invocation_increments_counter(self, sample_config_env):
        """Test that recording invocation increments counter."""
        from kube_medic.utils.helpers import (
            get_recursion_stats,
            _record_invocation,
        )

        initial_stats = get_recursion_stats()
        initial_count = initial_stats["total_invocations"]

        _record_invocation()

        final_stats = get_recursion_stats()
        assert final_stats["total_invocations"] == initial_count + 1
