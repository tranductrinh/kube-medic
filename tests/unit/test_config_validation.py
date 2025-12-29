"""
Tests for configuration validation.

Tests:
- LLM parameter validation (temperature, tokens)
- Prometheus parameter validation (timeout, max results)
- Kubernetes parameter validation (tail lines, max chars)
- Pydantic validator constraints
"""

import pytest
from pydantic import ValidationError


class TestConfigValidation:
    """Tests for configuration validation rules."""

    def test_llm_temperature_within_range(self) -> None:
        """Test that LLM temperature accepts valid range."""
        from kube_medic.config import get_settings
        get_settings.cache_clear()

        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
            "PROMETHEUS_URL": "http://prometheus:9090",
            "LLM_TEMPERATURE": "0.5",
        }):
            get_settings.cache_clear()
            settings = get_settings()
            assert settings.llm_temperature == 0.5

    def test_llm_temperature_out_of_range(self) -> None:
        """Test that invalid temperature raises error."""
        from kube_medic.config import Settings

        with pytest.raises(ValidationError):
            Settings(
                _env_file=None,
                azure_openai_endpoint="https://test.openai.azure.com",
                azure_openai_api_key="test-key",
                azure_openai_deployment_name="gpt-4o",
                prometheus_url="http://prometheus:9090",
                llm_temperature=5.0,  # Invalid: must be <= 2.0
            )

    def test_prometheus_timeout_positive(self) -> None:
        """Test that Prometheus timeout must be positive."""
        from kube_medic.config import Settings

        with pytest.raises(ValidationError):
            Settings(
                _env_file=None,
                azure_openai_endpoint="https://test.openai.azure.com",
                azure_openai_api_key="test-key",
                azure_openai_deployment_name="gpt-4o",
                prometheus_url="http://prometheus:9090",
                prometheus_timeout=0,  # Invalid: must be > 0
            )

    def test_k8s_logs_tail_lines_positive(self) -> None:
        """Test that K8s tail lines must be positive."""
        from kube_medic.config import Settings

        with pytest.raises(ValidationError):
            Settings(
                _env_file=None,
                azure_openai_endpoint="https://test.openai.azure.com",
                azure_openai_api_key="test-key",
                azure_openai_deployment_name="gpt-4o",
                prometheus_url="http://prometheus:9090",
                k8s_logs_tail_lines=-10,  # Invalid: must be > 0
            )

    def test_k8s_logs_max_chars_positive(self) -> None:
        """Test that K8s max chars must be positive."""
        from kube_medic.config import Settings

        with pytest.raises(ValidationError):
            Settings(
                _env_file=None,
                azure_openai_endpoint="https://test.openai.azure.com",
                azure_openai_api_key="test-key",
                azure_openai_deployment_name="gpt-4o",
                prometheus_url="http://prometheus:9090",
                k8s_logs_max_chars=0,  # Invalid: must be > 0
            )

    def test_all_default_values_provided(self) -> None:
        """Test that all optional settings have defaults."""
        from kube_medic.config import get_settings
        get_settings.cache_clear()

        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
            "PROMETHEUS_URL": "http://prometheus:9090",
        }):
            get_settings.cache_clear()
            settings = get_settings()

            # Check all optional settings have defaults
            assert settings.llm_temperature == 0.0
            assert settings.llm_max_tokens == 2048
            assert settings.prometheus_timeout == 10
            assert settings.prometheus_max_series_results == 20
            assert settings.k8s_logs_tail_lines == 50
            assert settings.k8s_logs_max_chars == 3000
            assert settings.text_truncate_max_length == 500

