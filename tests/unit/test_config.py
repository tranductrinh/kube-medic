"""
Unit tests for configuration module.

Tests:
- Configuration loading from environment variables
- URL normalization
- Required field validation
- Default values
- Settings caching
- Validation constraints
"""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError


class TestSettingsLoading:
    """Tests for settings loading from environment."""

    def test_loads_from_env(self) -> None:
        """Test that settings load from environment variables."""
        from kube_medic.config import get_settings
        get_settings.cache_clear()

        with patch.dict(os.environ, {
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
            "PROMETHEUS_URL": "http://prometheus:9090",
        }, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

            assert settings.azure_openai_endpoint == "https://test.openai.azure.com"
            assert settings.azure_openai_api_key == "test-key"
            assert settings.azure_openai_deployment_name == "gpt-4o"
            assert settings.prometheus_url == "http://prometheus:9090"

    def test_ignores_extra_env_vars(self) -> None:
        """Test that extra environment variables are ignored (extra='ignore')."""
        from kube_medic.config import get_settings
        get_settings.cache_clear()

        with patch.dict(os.environ, {
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
            "PROMETHEUS_URL": "http://prometheus:9090",
            "UNKNOWN_SETTING": "should-be-ignored",
        }, clear=True):
            get_settings.cache_clear()
            # Should not raise error for extra settings
            settings = get_settings()
            assert not hasattr(settings, "unknown_setting")


class TestSettingsCaching:
    """Tests for settings caching behavior (lru_cache)."""

    def test_get_settings_returns_cached_instance(self) -> None:
        """Test that get_settings returns cached instance."""
        from kube_medic.config import get_settings
        get_settings.cache_clear()

        with patch.dict(os.environ, {
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
            "PROMETHEUS_URL": "http://prometheus:9090",
        }, clear=True):
            get_settings.cache_clear()
            settings1 = get_settings()
            settings2 = get_settings()

            assert settings1 is settings2

    def test_cache_clear_creates_new_instance(self) -> None:
        """Test that cache_clear creates new instance."""
        from kube_medic.config import get_settings
        get_settings.cache_clear()

        with patch.dict(os.environ, {
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
            "PROMETHEUS_URL": "http://prometheus:9090",
        }, clear=True):
            get_settings.cache_clear()
            settings1 = get_settings()
            get_settings.cache_clear()
            settings2 = get_settings()

            # Different instances after cache clear
            assert settings1 is not settings2


class TestURLNormalization:
    """Tests for URL normalization (trailing slash removal)."""

    def test_removes_trailing_slash_from_endpoint(self) -> None:
        """Test that trailing slash is removed from Azure endpoint."""
        from kube_medic.config import get_settings
        get_settings.cache_clear()

        with patch.dict(os.environ, {
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
            "PROMETHEUS_URL": "http://prometheus:9090",
        }, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

            assert settings.azure_openai_endpoint == "https://test.openai.azure.com"

    def test_removes_trailing_slash_from_prometheus(self) -> None:
        """Test that trailing slash is removed from Prometheus URL."""
        from kube_medic.config import get_settings
        get_settings.cache_clear()

        with patch.dict(os.environ, {
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
            "PROMETHEUS_URL": "http://prometheus:9090/",
        }, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

            assert settings.prometheus_url == "http://prometheus:9090"

    def test_removes_multiple_trailing_slashes(self) -> None:
        """Test that multiple trailing slashes are removed."""
        from kube_medic.config import get_settings
        get_settings.cache_clear()

        with patch.dict(os.environ, {
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com///",
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
            "PROMETHEUS_URL": "http://prometheus:9090//",
        }, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

            assert settings.azure_openai_endpoint == "https://test.openai.azure.com"
            assert settings.prometheus_url == "http://prometheus:9090"


class TestRequiredFields:
    """Tests for required field validation."""

    def test_missing_azure_endpoint_raises_error(self) -> None:
        """Test that missing Azure endpoint raises error."""
        from kube_medic.config import Settings

        with pytest.raises(ValidationError) as exc_info:
            Settings(
                _env_file=None,
                azure_openai_api_key="test-key",
                azure_openai_deployment_name="gpt-4o",
                prometheus_url="http://prometheus:9090",
            )

        assert "azure_openai_endpoint" in str(exc_info.value)

    def test_missing_azure_api_key_raises_error(self) -> None:
        """Test that missing Azure API key raises error."""
        from kube_medic.config import Settings

        with pytest.raises(ValidationError) as exc_info:
            Settings(
                _env_file=None,
                azure_openai_endpoint="https://test.openai.azure.com",
                azure_openai_deployment_name="gpt-4o",
                prometheus_url="http://prometheus:9090",
            )

        assert "azure_openai_api_key" in str(exc_info.value)

    def test_missing_deployment_name_raises_error(self) -> None:
        """Test that missing deployment name raises error."""
        from kube_medic.config import Settings

        with pytest.raises(ValidationError) as exc_info:
            Settings(
                _env_file=None,
                azure_openai_endpoint="https://test.openai.azure.com",
                azure_openai_api_key="test-key",
                prometheus_url="http://prometheus:9090",
            )

        assert "azure_openai_deployment_name" in str(exc_info.value)

    def test_missing_prometheus_url_raises_error(self) -> None:
        """Test that missing Prometheus URL raises error."""
        from kube_medic.config import Settings

        with pytest.raises(ValidationError) as exc_info:
            Settings(
                _env_file=None,
                azure_openai_endpoint="https://test.openai.azure.com",
                azure_openai_api_key="test-key",
                azure_openai_deployment_name="gpt-4o",
            )

        assert "prometheus_url" in str(exc_info.value)


class TestDefaultValues:
    """Tests for default values."""

    def test_llm_defaults(self) -> None:
        """Test LLM default values."""
        from kube_medic.config import get_settings
        get_settings.cache_clear()

        with patch.dict(os.environ, {
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
            "PROMETHEUS_URL": "http://prometheus:9090",
        }, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

            assert settings.azure_openai_api_version == "2024-08-01-preview"
            assert settings.llm_temperature == 0.0
            assert settings.llm_max_tokens == 2048

    def test_prometheus_defaults(self) -> None:
        """Test Prometheus default values."""
        from kube_medic.config import get_settings
        get_settings.cache_clear()

        with patch.dict(os.environ, {
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
            "PROMETHEUS_URL": "http://prometheus:9090",
        }, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

            assert settings.prometheus_timeout == 10
            assert settings.prometheus_max_series_results == 20

    def test_kubernetes_defaults(self) -> None:
        """Test Kubernetes default values."""
        from kube_medic.config import get_settings
        get_settings.cache_clear()

        with patch.dict(os.environ, {
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
            "PROMETHEUS_URL": "http://prometheus:9090",
        }, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

            assert settings.k8s_logs_tail_lines == 50
            assert settings.k8s_logs_max_chars == 3000

    def test_text_formatting_defaults(self) -> None:
        """Test text formatting default values."""
        from kube_medic.config import get_settings
        get_settings.cache_clear()

        with patch.dict(os.environ, {
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
            "PROMETHEUS_URL": "http://prometheus:9090",
        }, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

            assert settings.text_truncate_max_length == 500

    def test_all_default_values_provided(self) -> None:
        """Test that all optional settings have defaults."""
        from kube_medic.config import get_settings
        get_settings.cache_clear()

        with patch.dict(os.environ, {
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
            "PROMETHEUS_URL": "http://prometheus:9090",
        }, clear=True):
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


class TestConfigValidation:
    """Tests for configuration validation rules (Pydantic constraints)."""

    def test_llm_temperature_accepts_zero(self) -> None:
        """Test that LLM temperature accepts 0 (ge=0.0)."""
        from kube_medic.config import Settings

        settings = Settings(
            _env_file=None,
            azure_openai_endpoint="https://test.openai.azure.com",
            azure_openai_api_key="test-key",
            azure_openai_deployment_name="gpt-4o",
            prometheus_url="http://prometheus:9090",
            llm_temperature=0.0,
        )

        assert settings.llm_temperature == 0.0

    def test_llm_temperature_accepts_max(self) -> None:
        """Test that LLM temperature accepts maximum value 2.0 (le=2.0)."""
        from kube_medic.config import Settings

        settings = Settings(
            _env_file=None,
            azure_openai_endpoint="https://test.openai.azure.com",
            azure_openai_api_key="test-key",
            azure_openai_deployment_name="gpt-4o",
            prometheus_url="http://prometheus:9090",
            llm_temperature=2.0,
        )

        assert settings.llm_temperature == 2.0

    def test_llm_temperature_accepts_midpoint(self) -> None:
        """Test that LLM temperature accepts values within range."""
        from kube_medic.config import get_settings
        get_settings.cache_clear()

        with patch.dict(os.environ, {
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
            "PROMETHEUS_URL": "http://prometheus:9090",
            "LLM_TEMPERATURE": "0.5",
        }, clear=True):
            get_settings.cache_clear()
            settings = get_settings()
            assert settings.llm_temperature == 0.5

    def test_llm_temperature_rejects_negative(self) -> None:
        """Test that negative temperature raises error (ge=0.0)."""
        from kube_medic.config import Settings

        with pytest.raises(ValidationError):
            Settings(
                _env_file=None,
                azure_openai_endpoint="https://test.openai.azure.com",
                azure_openai_api_key="test-key",
                azure_openai_deployment_name="gpt-4o",
                prometheus_url="http://prometheus:9090",
                llm_temperature=-0.5,
            )

    def test_llm_temperature_rejects_above_max(self) -> None:
        """Test that temperature above 2.0 raises error (le=2.0)."""
        from kube_medic.config import Settings

        with pytest.raises(ValidationError):
            Settings(
                _env_file=None,
                azure_openai_endpoint="https://test.openai.azure.com",
                azure_openai_api_key="test-key",
                azure_openai_deployment_name="gpt-4o",
                prometheus_url="http://prometheus:9090",
                llm_temperature=2.5,
            )

    def test_llm_temperature_way_out_of_range(self) -> None:
        """Test that temperature of 5.0 raises error."""
        from kube_medic.config import Settings

        with pytest.raises(ValidationError):
            Settings(
                _env_file=None,
                azure_openai_endpoint="https://test.openai.azure.com",
                azure_openai_api_key="test-key",
                azure_openai_deployment_name="gpt-4o",
                prometheus_url="http://prometheus:9090",
                llm_temperature=5.0,
            )

    def test_llm_max_tokens_must_be_positive(self) -> None:
        """Test that max tokens must be positive (gt=0)."""
        from kube_medic.config import Settings

        with pytest.raises(ValidationError):
            Settings(
                _env_file=None,
                azure_openai_endpoint="https://test.openai.azure.com",
                azure_openai_api_key="test-key",
                azure_openai_deployment_name="gpt-4o",
                prometheus_url="http://prometheus:9090",
                llm_max_tokens=0,
            )

    def test_prometheus_timeout_must_be_positive(self) -> None:
        """Test that Prometheus timeout must be positive (gt=0)."""
        from kube_medic.config import Settings

        with pytest.raises(ValidationError):
            Settings(
                _env_file=None,
                azure_openai_endpoint="https://test.openai.azure.com",
                azure_openai_api_key="test-key",
                azure_openai_deployment_name="gpt-4o",
                prometheus_url="http://prometheus:9090",
                prometheus_timeout=0,
            )

    def test_prometheus_max_series_must_be_positive(self) -> None:
        """Test that Prometheus max series must be positive (gt=0)."""
        from kube_medic.config import Settings

        with pytest.raises(ValidationError):
            Settings(
                _env_file=None,
                azure_openai_endpoint="https://test.openai.azure.com",
                azure_openai_api_key="test-key",
                azure_openai_deployment_name="gpt-4o",
                prometheus_url="http://prometheus:9090",
                prometheus_max_series_results=-1,
            )

    def test_k8s_tail_lines_must_be_positive(self) -> None:
        """Test that K8s tail lines must be positive (gt=0)."""
        from kube_medic.config import Settings

        with pytest.raises(ValidationError):
            Settings(
                _env_file=None,
                azure_openai_endpoint="https://test.openai.azure.com",
                azure_openai_api_key="test-key",
                azure_openai_deployment_name="gpt-4o",
                prometheus_url="http://prometheus:9090",
                k8s_logs_tail_lines=0,
            )

    def test_k8s_tail_lines_rejects_negative(self) -> None:
        """Test that K8s tail lines rejects negative values."""
        from kube_medic.config import Settings

        with pytest.raises(ValidationError):
            Settings(
                _env_file=None,
                azure_openai_endpoint="https://test.openai.azure.com",
                azure_openai_api_key="test-key",
                azure_openai_deployment_name="gpt-4o",
                prometheus_url="http://prometheus:9090",
                k8s_logs_tail_lines=-10,
            )

    def test_k8s_max_chars_must_be_positive(self) -> None:
        """Test that K8s max chars must be positive (gt=0)."""
        from kube_medic.config import Settings

        with pytest.raises(ValidationError):
            Settings(
                _env_file=None,
                azure_openai_endpoint="https://test.openai.azure.com",
                azure_openai_api_key="test-key",
                azure_openai_deployment_name="gpt-4o",
                prometheus_url="http://prometheus:9090",
                k8s_logs_max_chars=0,
            )

    def test_text_truncate_length_must_be_positive(self) -> None:
        """Test that text truncate length must be positive (gt=0)."""
        from kube_medic.config import Settings

        with pytest.raises(ValidationError):
            Settings(
                _env_file=None,
                azure_openai_endpoint="https://test.openai.azure.com",
                azure_openai_api_key="test-key",
                azure_openai_deployment_name="gpt-4o",
                prometheus_url="http://prometheus:9090",
                text_truncate_max_length=0,
            )


class TestCustomValues:
    """Tests for custom (non-default) values from environment."""

    def test_custom_llm_settings(self) -> None:
        """Test that custom LLM settings are applied."""
        from kube_medic.config import get_settings
        get_settings.cache_clear()

        with patch.dict(os.environ, {
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
            "PROMETHEUS_URL": "http://prometheus:9090",
            "LLM_TEMPERATURE": "0.7",
            "LLM_MAX_TOKENS": "4096",
        }, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

            assert settings.llm_temperature == 0.7
            assert settings.llm_max_tokens == 4096

    def test_custom_prometheus_settings(self) -> None:
        """Test that custom Prometheus settings are applied."""
        from kube_medic.config import get_settings
        get_settings.cache_clear()

        with patch.dict(os.environ, {
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
            "PROMETHEUS_URL": "http://prometheus:9090",
            "PROMETHEUS_TIMEOUT": "30",
            "PROMETHEUS_MAX_SERIES_RESULTS": "50",
        }, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

            assert settings.prometheus_timeout == 30
            assert settings.prometheus_max_series_results == 50

    def test_custom_kubernetes_settings(self) -> None:
        """Test that custom Kubernetes settings are applied."""
        from kube_medic.config import get_settings
        get_settings.cache_clear()

        with patch.dict(os.environ, {
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
            "PROMETHEUS_URL": "http://prometheus:9090",
            "K8S_LOGS_TAIL_LINES": "100",
            "K8S_LOGS_MAX_CHARS": "5000",
        }, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

            assert settings.k8s_logs_tail_lines == 100
            assert settings.k8s_logs_max_chars == 5000

    def test_custom_api_version(self) -> None:
        """Test that custom API version is applied."""
        from kube_medic.config import get_settings
        get_settings.cache_clear()

        with patch.dict(os.environ, {
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
            "PROMETHEUS_URL": "http://prometheus:9090",
            "AZURE_OPENAI_API_VERSION": "2024-10-01",
        }, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

            assert settings.azure_openai_api_version == "2024-10-01"
