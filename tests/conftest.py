"""
Shared pytest configuration and fixtures for all tests.

This file is automatically discovered by pytest and provides:
- Common fixtures
- Test configuration
- Pytest plugins setup
"""

import os
import pytest


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as requiring live services"
    )


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear the settings cache before each test.

    This ensures tests don't interfere with each other when
    modifying environment variables.
    """
    from kube_medic.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def reset_kubernetes_module_state():
    """Reset kubernetes module singletons and cache between tests.

    This prevents tests from interfering with each other via:
    - Cached API clients
    - Cached API responses
    """
    import kube_medic.tools.kubernetes as k8s_module

    # Reset singletons
    k8s_module._v1_client = None
    k8s_module._apps_client = None
    k8s_module._networking_client = None

    # Reset cache
    k8s_module._k8s_cache = None

    yield

    # Reset after test as well
    k8s_module._v1_client = None
    k8s_module._apps_client = None
    k8s_module._networking_client = None
    k8s_module._k8s_cache = None


@pytest.fixture(autouse=True)
def reset_prometheus_module_state():
    """Reset prometheus module singletons and cache between tests.

    This prevents tests from interfering with each other via:
    - Cached Prometheus client
    - Cached query results
    """
    import kube_medic.tools.prometheus as prom_module

    # Reset singleton
    prom_module._prom_client = None

    # Reset cache
    prom_module._query_cache = None

    yield

    # Reset after test as well
    prom_module._prom_client = None
    prom_module._query_cache = None


@pytest.fixture
def mock_env(monkeypatch):
    """Fixture for safely mocking environment variables.

    Usage:
        def test_something(mock_env):
            mock_env.set("VAR_NAME", "value")
            # Test code here
    """
    class MockEnv:
        def __init__(self, monkeypatch):
            self.monkeypatch = monkeypatch

        def set(self, key: str, value: str):
            self.monkeypatch.setenv(key, value)

        def unset(self, key: str):
            self.monkeypatch.delenv(key, raising=False)

    return MockEnv(monkeypatch)


@pytest.fixture
def sample_config_env(mock_env):
    """Fixture providing a valid configuration environment.

    Usage:
        def test_something(sample_config_env):
            # Config env is already set up
            settings = get_settings()
    """
    mock_env.set("OPENAI_BASE_URL", "https://test.openai.azure.com/openai/v1/")
    mock_env.set("OPENAI_API_KEY", "test-key")
    mock_env.set("OPENAI_MODEL", "gpt-5.2")
    mock_env.set("PROMETHEUS_URL", "http://prometheus:9090")
    mock_env.set("SMTP_HOST", "smtp.test.com")
    mock_env.set("EMAIL_FROM", "test@test.com")
    mock_env.set("EMAIL_TO", "recipient@test.com")
    return mock_env


# =============================================================================
# HOOKS
# =============================================================================

def pytest_collection_modifyitems(config, items):
    """Automatically mark integration tests based on file name.

    Tests in test_integration.py are automatically marked with @pytest.mark.integration
    """
    for item in items:
        if "test_integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

