"""
Tests for Network connectivity tools.

Tests:
- HTTP check functionality
- Error handling (timeout, SSL, connection errors)
- Response parsing
"""

from unittest.mock import MagicMock, patch

import pytest


class TestHttpCheck:
    """Tests for http_check tool."""

    @patch("kube_medic.tools.network.requests.request")
    def test_successful_request(self, mock_request) -> None:
        """Test http_check returns success for 200 response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.reason = "OK"
        mock_response.elapsed.total_seconds.return_value = 0.150
        mock_response.history = []
        mock_response.headers = {"content-type": "application/json"}
        mock_request.return_value = mock_response

        from kube_medic.tools.network import http_check

        result = http_check.invoke({"url": "https://example.com/health"})

        assert "200 OK" in result
        assert "150ms" in result
        assert "OK - Endpoint is accessible" in result

    @patch("kube_medic.tools.network.requests.request")
    def test_shows_redirect_info(self, mock_request) -> None:
        """Test http_check shows redirect information."""
        mock_redirect = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.reason = "OK"
        mock_response.elapsed.total_seconds.return_value = 0.200
        mock_response.history = [mock_redirect]
        mock_response.url = "https://example.com/final"
        mock_response.headers = {}
        mock_request.return_value = mock_response

        from kube_medic.tools.network import http_check

        result = http_check.invoke({"url": "https://example.com"})

        assert "Redirects: 1" in result
        assert "Final URL: https://example.com/final" in result

    @patch("kube_medic.tools.network.requests.request")
    def test_client_error_response(self, mock_request) -> None:
        """Test http_check handles 4xx responses."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.reason = "Not Found"
        mock_response.elapsed.total_seconds.return_value = 0.100
        mock_response.history = []
        mock_response.headers = {}
        mock_request.return_value = mock_response

        from kube_medic.tools.network import http_check

        result = http_check.invoke({"url": "https://example.com/notfound"})

        assert "404 Not Found" in result
        assert "CLIENT ERROR" in result

    @patch("kube_medic.tools.network.requests.request")
    def test_server_error_response(self, mock_request) -> None:
        """Test http_check handles 5xx responses."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.reason = "Service Unavailable"
        mock_response.elapsed.total_seconds.return_value = 0.050
        mock_response.history = []
        mock_response.headers = {}
        mock_request.return_value = mock_response

        from kube_medic.tools.network import http_check

        result = http_check.invoke({"url": "https://example.com/api"})

        assert "503 Service Unavailable" in result
        assert "SERVER ERROR" in result

    @patch("kube_medic.tools.network.requests.request")
    def test_timeout_error(self, mock_request) -> None:
        """Test http_check handles timeout."""
        import requests

        mock_request.side_effect = requests.exceptions.Timeout()

        from kube_medic.tools.network import http_check

        result = http_check.invoke({"url": "https://slow.example.com", "timeout": 5})

        assert "TIMEOUT" in result
        assert "5s" in result

    @patch("kube_medic.tools.network.requests.request")
    def test_ssl_error(self, mock_request) -> None:
        """Test http_check handles SSL errors."""
        import requests

        mock_request.side_effect = requests.exceptions.SSLError("certificate verify failed")

        from kube_medic.tools.network import http_check

        result = http_check.invoke({"url": "https://invalid-cert.example.com"})

        assert "SSL ERROR" in result
        assert "verify_ssl=False" in result

    @patch("kube_medic.tools.network.requests.request")
    def test_connection_error(self, mock_request) -> None:
        """Test http_check handles connection errors."""
        import requests

        mock_request.side_effect = requests.exceptions.ConnectionError("Connection refused")

        from kube_medic.tools.network import http_check

        result = http_check.invoke({"url": "https://unreachable.example.com"})

        assert "CONNECTION ERROR" in result

    @patch("kube_medic.tools.network.requests.request")
    def test_custom_method(self, mock_request) -> None:
        """Test http_check with custom HTTP method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.reason = "OK"
        mock_response.elapsed.total_seconds.return_value = 0.100
        mock_response.history = []
        mock_response.headers = {}
        mock_request.return_value = mock_response

        from kube_medic.tools.network import http_check

        http_check.invoke({"url": "https://example.com", "method": "HEAD"})

        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["method"] == "HEAD"

    @patch("kube_medic.tools.network.requests.request")
    def test_verify_ssl_false(self, mock_request) -> None:
        """Test http_check with SSL verification disabled."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.reason = "OK"
        mock_response.elapsed.total_seconds.return_value = 0.100
        mock_response.history = []
        mock_response.headers = {}
        mock_request.return_value = mock_response

        from kube_medic.tools.network import http_check

        http_check.invoke({"url": "https://example.com", "verify_ssl": False})

        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["verify"] is False

    @patch("kube_medic.tools.network.requests.request")
    def test_shows_relevant_headers(self, mock_request) -> None:
        """Test http_check shows relevant response headers."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.reason = "OK"
        mock_response.elapsed.total_seconds.return_value = 0.100
        mock_response.history = []
        mock_response.headers = {
            "content-type": "application/json",
            "server": "nginx",
            "x-powered-by": "Express",
        }
        mock_request.return_value = mock_response

        from kube_medic.tools.network import http_check

        result = http_check.invoke({"url": "https://api.example.com"})

        assert "content-type: application/json" in result
        assert "server: nginx" in result

    @patch("kube_medic.tools.network.requests.request")
    def test_redirect_response(self, mock_request) -> None:
        """Test http_check handles redirect status codes."""
        mock_response = MagicMock()
        mock_response.status_code = 301
        mock_response.reason = "Moved Permanently"
        mock_response.elapsed.total_seconds.return_value = 0.050
        mock_response.history = []
        mock_response.headers = {}
        mock_request.return_value = mock_response

        from kube_medic.tools.network import http_check

        result = http_check.invoke({
            "url": "https://old.example.com",
            "follow_redirects": False
        })

        assert "301 Moved Permanently" in result
        assert "REDIRECT" in result


class TestNetworkToolsList:
    """Tests for network_tools list."""

    def test_all_tools_in_list(self) -> None:
        """Test that all network tools are in the tools list."""
        from kube_medic.tools.network import network_tools, http_check

        assert http_check in network_tools
        assert len(network_tools) == 1

    def test_tools_have_names(self) -> None:
        """Test that all tools have proper names."""
        from kube_medic.tools.network import network_tools

        expected_names = ["http_check"]
        tool_names = [t.name for t in network_tools]

        for name in expected_names:
            assert name in tool_names
