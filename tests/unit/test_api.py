"""
Tests for API module.

Tests:
- Helper functions (generate_thread_id, format_payload_as_query)
- Alertmanager payload formatting
- API endpoints (health, webhook, query)
"""

from unittest.mock import MagicMock, patch

import pytest

from kube_medic.api import (
    generate_thread_id,
    format_payload_as_query,
    _format_alertmanager_payload,
    WebhookResponse,
    QueryRequest,
    QueryResponse,
    HealthResponse,
)


class TestGenerateThreadId:
    """Tests for generate_thread_id function."""

    def test_generates_deterministic_id(self) -> None:
        """Test that same payload generates same thread ID."""
        payload = {"alert": "test", "value": 123}

        id1 = generate_thread_id(payload)
        id2 = generate_thread_id(payload)

        assert id1 == id2

    def test_different_payloads_generate_different_ids(self) -> None:
        """Test that different payloads generate different IDs."""
        payload1 = {"alert": "test1"}
        payload2 = {"alert": "test2"}

        id1 = generate_thread_id(payload1)
        id2 = generate_thread_id(payload2)

        assert id1 != id2

    def test_id_has_webhook_prefix(self) -> None:
        """Test that thread ID has 'webhook-' prefix."""
        payload = {"test": "data"}

        thread_id = generate_thread_id(payload)

        assert thread_id.startswith("webhook-")

    def test_handles_nested_payload(self) -> None:
        """Test that nested payloads work correctly."""
        payload = {
            "alerts": [
                {"status": "firing", "labels": {"name": "test"}}
            ]
        }

        thread_id = generate_thread_id(payload)

        assert thread_id.startswith("webhook-")
        assert len(thread_id) == len("webhook-") + 12  # 12 hex chars


class TestFormatPayloadAsQuery:
    """Tests for format_payload_as_query function."""

    def test_generic_payload_formatted_as_json(self) -> None:
        """Test that generic payloads are formatted as JSON."""
        payload = {"issue": "High latency", "service": "api"}

        query = format_payload_as_query(payload)

        assert "webhook has been received" in query.lower()
        assert "High latency" in query
        assert "api" in query
        assert "```json" in query

    def test_alertmanager_payload_detected(self) -> None:
        """Test that Alertmanager payloads are detected."""
        payload = {
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"alertname": "TestAlert"},
                    "annotations": {"description": "Test description"}
                }
            ]
        }

        query = format_payload_as_query(payload)

        assert "alert has fired" in query.lower()
        assert "TestAlert" in query

    def test_empty_payload_still_formats(self) -> None:
        """Test that empty payload still generates a query."""
        payload = {}

        query = format_payload_as_query(payload)

        assert "webhook has been received" in query.lower()


class TestFormatAlertmanagerPayload:
    """Tests for _format_alertmanager_payload function."""

    def test_single_firing_alert(self) -> None:
        """Test formatting of single firing alert."""
        payload = {
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "HighCPU",
                        "severity": "warning",
                        "namespace": "production",
                        "pod": "my-pod"
                    },
                    "annotations": {
                        "description": "CPU usage is high"
                    }
                }
            ]
        }

        query = _format_alertmanager_payload(payload)

        assert "HighCPU" in query
        assert "warning" in query
        assert "production" in query
        assert "my-pod" in query
        assert "CPU usage is high" in query

    def test_multiple_firing_alerts(self) -> None:
        """Test formatting of multiple firing alerts."""
        payload = {
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"alertname": "Alert1", "severity": "warning"},
                    "annotations": {"description": "First alert"}
                },
                {
                    "status": "firing",
                    "labels": {"alertname": "Alert2", "severity": "critical"},
                    "annotations": {"description": "Second alert"}
                }
            ]
        }

        query = _format_alertmanager_payload(payload)

        assert "Multiple alerts" in query
        assert "Alert1" in query
        assert "Alert2" in query
        assert "2" in query  # Total count

    def test_resolved_alerts_ignored(self) -> None:
        """Test that resolved alerts are ignored."""
        payload = {
            "alerts": [
                {
                    "status": "resolved",
                    "labels": {"alertname": "ResolvedAlert"},
                    "annotations": {}
                }
            ]
        }

        query = _format_alertmanager_payload(payload)

        assert query == ""

    def test_mixed_status_only_firing_processed(self) -> None:
        """Test that only firing alerts are processed."""
        payload = {
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"alertname": "FiringAlert"},
                    "annotations": {"description": "Active"}
                },
                {
                    "status": "resolved",
                    "labels": {"alertname": "ResolvedAlert"},
                    "annotations": {}
                }
            ]
        }

        query = _format_alertmanager_payload(payload)

        assert "FiringAlert" in query
        assert "ResolvedAlert" not in query

    def test_uses_summary_if_no_description(self) -> None:
        """Test that summary is used if description is missing."""
        payload = {
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"alertname": "TestAlert"},
                    "annotations": {"summary": "Summary text"}
                }
            ]
        }

        query = _format_alertmanager_payload(payload)

        assert "Summary text" in query

    def test_default_values_for_missing_labels(self) -> None:
        """Test default values when labels are missing."""
        payload = {
            "alerts": [
                {
                    "status": "firing",
                    "labels": {},
                    "annotations": {}
                }
            ]
        }

        query = _format_alertmanager_payload(payload)

        assert "Unknown Alert" in query
        assert "unknown" in query  # severity
        assert "cluster-wide" in query  # context

    def test_context_with_service_label(self) -> None:
        """Test context includes service when present."""
        payload = {
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "Test",
                        "service": "my-service"
                    },
                    "annotations": {}
                }
            ]
        }

        query = _format_alertmanager_payload(payload)

        assert "service=my-service" in query


class TestPydanticModels:
    """Tests for Pydantic response models."""

    def test_webhook_response_model(self) -> None:
        """Test WebhookResponse model."""
        response = WebhookResponse(status="ok")

        assert response.status == "ok"

    def test_query_request_model(self) -> None:
        """Test QueryRequest model with defaults."""
        request = QueryRequest(question="What pods are failing?")

        assert request.question == "What pods are failing?"
        assert request.thread_id == "default"

    def test_query_request_custom_thread_id(self) -> None:
        """Test QueryRequest with custom thread_id."""
        request = QueryRequest(
            question="Check logs",
            thread_id="custom-123"
        )

        assert request.thread_id == "custom-123"

    def test_query_response_model(self) -> None:
        """Test QueryResponse model."""
        response = QueryResponse(
            response="Analysis complete",
            thread_id="test-123"
        )

        assert response.response == "Analysis complete"
        assert response.thread_id == "test-123"

    def test_health_response_model(self) -> None:
        """Test HealthResponse model."""
        response = HealthResponse(status="healthy", agent_ready=True)

        assert response.status == "healthy"
        assert response.agent_ready is True


class TestApiEndpoints:
    """Tests for API endpoints using FastAPI TestClient."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked agent (bypassing lifespan)."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from kube_medic.api import (
            app_state,
            health_check,
            webhook,
            webhook_sync,
            query_agent,
            WebhookResponse,
            QueryResponse,
            HealthResponse,
        )

        # Create a test app without the lifespan that initializes real agent
        test_app = FastAPI()
        test_app.get("/health", response_model=HealthResponse)(health_check)
        test_app.post("/webhook", response_model=WebhookResponse)(webhook)
        test_app.post("/webhook/sync", response_model=QueryResponse)(webhook_sync)
        test_app.post("/query", response_model=QueryResponse)(query_agent)

        # Mock the agent
        app_state.agent = MagicMock()

        with TestClient(test_app, raise_server_exceptions=False) as client:
            yield client

        # Cleanup
        app_state.agent = None

    @pytest.fixture
    def client_no_agent(self):
        """Create test client without agent initialized."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from kube_medic.api import (
            app_state,
            health_check,
            webhook,
            webhook_sync,
            query_agent,
            WebhookResponse,
            QueryResponse,
            HealthResponse,
        )

        # Create a test app without the lifespan
        test_app = FastAPI()
        test_app.get("/health", response_model=HealthResponse)(health_check)
        test_app.post("/webhook", response_model=WebhookResponse)(webhook)
        test_app.post("/webhook/sync", response_model=QueryResponse)(webhook_sync)
        test_app.post("/query", response_model=QueryResponse)(query_agent)

        # Ensure agent is None
        app_state.agent = None

        with TestClient(test_app, raise_server_exceptions=False) as client:
            yield client

    def test_health_endpoint(self, client) -> None:
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["agent_ready"] is True

    def test_health_endpoint_agent_not_ready(self, client_no_agent) -> None:
        """Test health check when agent not initialized."""
        response = client_no_agent.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["agent_ready"] is False

    def test_webhook_endpoint_returns_ok(self, client) -> None:
        """Test webhook endpoint returns ok immediately."""
        payload = {"issue": "test issue"}

        response = client.post("/webhook", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_webhook_endpoint_agent_not_initialized(self, client_no_agent) -> None:
        """Test webhook returns 503 when agent not initialized."""
        response = client_no_agent.post("/webhook", json={"test": "data"})

        assert response.status_code == 503

    def test_query_endpoint_agent_not_initialized(self, client_no_agent) -> None:
        """Test query returns 503 when agent not initialized."""
        response = client_no_agent.post(
            "/query",
            json={"question": "test question"}
        )

        assert response.status_code == 503

    @patch("kube_medic.api.ask_agent")
    def test_query_endpoint_calls_agent(self, mock_invoke, client) -> None:
        """Test query endpoint calls ask_agent."""
        mock_invoke.return_value = "Agent response"

        response = client.post(
            "/query",
            json={"question": "Why is my pod crashing?"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "Agent response"
        mock_invoke.assert_called_once()

    @patch("kube_medic.api.ask_agent")
    def test_webhook_sync_endpoint(self, mock_invoke, client) -> None:
        """Test synchronous webhook endpoint."""
        mock_invoke.return_value = "Investigation complete"

        payload = {"issue": "High latency", "service": "api"}
        response = client.post("/webhook/sync", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "Investigation complete" in data["response"]

    def test_webhook_sync_no_firing_alerts(self, client) -> None:
        """Test sync webhook with only resolved alerts returns appropriate message."""
        payload = {
            "alerts": [
                {"status": "resolved", "labels": {"alertname": "Test"}}
            ]
        }

        response = client.post("/webhook/sync", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "No actionable content" in data["response"]


class TestProcessPayloadBackground:
    """Tests for background processing function."""

    @patch("kube_medic.api.ask_agent")
    @patch("kube_medic.api.app_state")
    def test_background_processing_calls_agent(
            self,
            mock_app_state,
            mock_invoke
    ) -> None:
        """Test background processing calls ask_agent."""
        from kube_medic.api import process_payload_background

        mock_app_state.agent = MagicMock()
        mock_invoke.return_value = "Response"

        payload = {"issue": "test"}
        process_payload_background(payload, "thread-123")

        mock_invoke.assert_called_once()

    @patch("kube_medic.api.ask_agent")
    @patch("kube_medic.api.app_state")
    def test_background_processing_handles_empty_query(
            self,
            mock_app_state,
            mock_invoke
    ) -> None:
        """Test background processing handles empty query gracefully."""
        from kube_medic.api import process_payload_background

        mock_app_state.agent = MagicMock()

        # Alertmanager payload with only resolved alerts -> empty query
        payload = {
            "alerts": [{"status": "resolved", "labels": {}}]
        }
        process_payload_background(payload, "thread-123")

        mock_invoke.assert_not_called()

    @patch("kube_medic.api.ask_agent")
    @patch("kube_medic.api.app_state")
    def test_background_processing_handles_exception(
            self,
            mock_app_state,
            mock_invoke
    ) -> None:
        """Test background processing handles exceptions gracefully."""
        from kube_medic.api import process_payload_background

        mock_app_state.agent = MagicMock()
        mock_invoke.side_effect = Exception("Agent error")

        payload = {"issue": "test"}

        # Should not raise
        process_payload_background(payload, "thread-123")
