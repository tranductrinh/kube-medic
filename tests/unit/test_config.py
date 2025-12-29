"""
Unit tests for configuration module.

Tests:
- Configuration loading from environment variables
- URL normalization
- Required field validation
- Default values
"""

import os
from unittest.mock import patch

import pytest


class TestConfig:
    """Tests for configuration loading and defaults."""

    def test_settings_loads_from_env(self) -> None:
        """Test that settings load from environment variables."""
        from kube_medic.config import get_settings
        get_settings.cache_clear()

        with patch.dict(os.environ, {
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
            "PROMETHEUS_URL": "http://prometheus:9090",
        }):
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

