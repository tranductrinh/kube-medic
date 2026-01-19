"""
Integration tests for API endpoints and reliability features.

Tests that validate:
- Webhook processing with rate limiting
- Admin endpoints for monitoring
- Retry logic and dead letter queue
- Caching behavior

Run with: pytest tests/integration/test_api_integration.py -v
"""

import os
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_agent():
    """Create a mock agent for testing."""
    agent = MagicMock()
    # Mock the stream method to return a simple response
    agent.stream.return_value = iter([
        {"agent": {"messages": [MagicMock(
            type="ai",
            content="Test response",
            tool_calls=None,
        )]}}
    ])
    # Ensure checkpointer doesn't return MagicMock for get_stats
    # (which would fail pydantic validation in AdminStatsResponse)
    agent.checkpointer = None
    return agent


@pytest.fixture
def client(mock_agent, sample_config_env):
    """Create a test client with mocked agent."""
    with patch('kube_medic.api.create_supervisor_agent') as mock_create:
        mock_create.return_value = mock_agent
        from kube_medic.api import app, app_state
        app_state.agent = mock_agent
        with TestClient(app) as c:
            yield c


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_returns_200(self, client):
        """Test that health endpoint returns 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_shows_agent_ready(self, client):
        """Test that health endpoint shows agent is ready."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"
        assert data["agent_ready"] is True


class TestWebhookEndpoint:
    """Tests for the webhook endpoint."""

    def test_webhook_accepts_alertmanager_payload(self, client):
        """Test that Alertmanager webhooks are accepted."""
        payload = {
            "alerts": [{
                "status": "firing",
                "labels": {
                    "alertname": "TestAlert",
                    "severity": "warning",
                    "namespace": "default",
                },
                "annotations": {
                    "description": "Test alert description",
                },
            }]
        }
        response = client.post("/webhook", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_webhook_accepts_generic_payload(self, client):
        """Test that generic webhooks are accepted."""
        payload = {
            "event": "pod_crash",
            "namespace": "production",
            "pod": "app-123",
        }
        response = client.post("/webhook", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_webhook_returns_503_when_agent_not_ready(self, client):
        """Test 503 when agent is not initialized."""
        from kube_medic.api import app_state
        original_agent = app_state.agent
        app_state.agent = None

        response = client.post("/webhook", json={"test": "data"})
        assert response.status_code == 503

        app_state.agent = original_agent

    def test_webhook_sync_returns_response(self, client, mock_agent):
        """Test that sync webhook returns agent response."""
        payload = {"event": "test"}
        response = client.post("/webhook/sync", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "thread_id" in data


class TestQueryEndpoint:
    """Tests for the direct query endpoint."""

    def test_query_accepts_valid_request(self, client):
        """Test that query endpoint accepts valid requests."""
        response = client.post("/query", json={
            "question": "What pods are running?",
            "thread_id": "test-thread",
        })
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert data["thread_id"] == "test-thread"

    def test_query_uses_default_thread_id(self, client):
        """Test that query uses default thread_id if not provided."""
        response = client.post("/query", json={
            "question": "What is the cluster status?",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["thread_id"] == "default"


class TestAdminEndpoints:
    """Tests for admin/monitoring endpoints."""

    def test_admin_stats_returns_data(self, client):
        """Test that admin stats endpoint returns statistics."""
        response = client.get("/admin/stats")
        assert response.status_code == 200
        data = response.json()
        assert "webhook_stats" in data
        assert "failed_webhook_count" in data
        assert "recursion_stats" in data

    def test_admin_failed_webhooks_empty_initially(self, client):
        """Test that failed webhooks list is empty initially."""
        from kube_medic.api import app_state
        app_state.failed_webhooks.clear()

        response = client.get("/admin/failed-webhooks")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["failures"] == []

    def test_admin_clear_failed_webhooks(self, client):
        """Test that clearing failed webhooks works."""
        from kube_medic.api import app_state, FailedWebhook

        # Add a test failure
        app_state.failed_webhooks.append(FailedWebhook(
            thread_id="test-123",
            payload={"test": "data"},
            error="Test error",
            timestamp="2024-01-01T00:00:00",
            retry_count=3,
        ))

        response = client.delete("/admin/failed-webhooks")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        # Verify cleared
        response = client.get("/admin/failed-webhooks")
        assert response.json()["count"] == 0


class TestPayloadFormatting:
    """Tests for webhook payload formatting."""

    def test_alertmanager_single_alert_formatting(self, sample_config_env):
        """Test formatting of single Alertmanager alert."""
        from kube_medic.api import format_payload_as_query

        payload = {
            "alerts": [{
                "status": "firing",
                "labels": {
                    "alertname": "HighCPU",
                    "severity": "critical",
                    "namespace": "production",
                    "pod": "app-server-1",
                },
                "annotations": {
                    "description": "CPU usage is above 90%",
                },
            }]
        }

        result = format_payload_as_query(payload)

        assert "HighCPU" in result
        assert "critical" in result
        assert "production" in result
        assert "CPU usage is above 90%" in result

    def test_alertmanager_multiple_alerts_formatting(self, sample_config_env):
        """Test formatting of multiple Alertmanager alerts."""
        from kube_medic.api import format_payload_as_query

        payload = {
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"alertname": "Alert1", "severity": "warning"},
                    "annotations": {"description": "First alert"},
                },
                {
                    "status": "firing",
                    "labels": {"alertname": "Alert2", "severity": "critical"},
                    "annotations": {"description": "Second alert"},
                },
            ]
        }

        result = format_payload_as_query(payload)

        assert "Multiple alerts" in result
        assert "Alert1" in result
        assert "Alert2" in result
        assert "2" in result  # Total count

    def test_alertmanager_resolved_alerts_ignored(self, sample_config_env):
        """Test that resolved alerts are ignored."""
        from kube_medic.api import format_payload_as_query

        payload = {
            "alerts": [{
                "status": "resolved",
                "labels": {"alertname": "ResolvedAlert"},
                "annotations": {"description": "This was resolved"},
            }]
        }

        result = format_payload_as_query(payload)
        assert result == ""  # Should return empty string for resolved alerts

    def test_generic_payload_formatting(self, sample_config_env):
        """Test formatting of generic payload."""
        from kube_medic.api import format_payload_as_query

        payload = {
            "event": "deployment_failed",
            "namespace": "staging",
            "message": "Deployment timed out",
        }

        result = format_payload_as_query(payload)

        assert "webhook" in result.lower()
        assert "deployment_failed" in result
        assert "staging" in result


class TestThreadIdGeneration:
    """Tests for deterministic thread ID generation."""

    def test_same_payload_same_thread_id(self, sample_config_env):
        """Test that same payload generates same thread ID."""
        from kube_medic.api import generate_thread_id

        payload = {"event": "test", "namespace": "default"}

        id1 = generate_thread_id(payload)
        id2 = generate_thread_id(payload)

        assert id1 == id2

    def test_different_payload_different_thread_id(self, sample_config_env):
        """Test that different payloads generate different thread IDs."""
        from kube_medic.api import generate_thread_id

        payload1 = {"event": "test1"}
        payload2 = {"event": "test2"}

        id1 = generate_thread_id(payload1)
        id2 = generate_thread_id(payload2)

        assert id1 != id2

    def test_thread_id_format(self, sample_config_env):
        """Test that thread ID has expected format."""
        from kube_medic.api import generate_thread_id

        payload = {"event": "test"}
        thread_id = generate_thread_id(payload)

        assert thread_id.startswith("webhook-")
        assert len(thread_id) == len("webhook-") + 12  # 12 char hash
