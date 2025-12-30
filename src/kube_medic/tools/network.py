"""
Network Connectivity Tools.

This module provides tools for checking network connectivity and HTTP endpoints.

Tools:
- http_check: Check HTTP/HTTPS endpoint accessibility
"""

import requests
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from requests.exceptions import RequestException

from kube_medic.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# INPUT SCHEMAS
# =============================================================================

class HttpCheckInput(BaseModel):
    """Input schema for HTTP check."""

    url: str = Field(
        ...,
        description="The URL to check (e.g., 'https://api.example.com/health')"
    )
    method: str = Field(
        default="GET",
        description="HTTP method to use (GET, HEAD, POST, etc.)"
    )
    timeout: int = Field(
        default=10,
        description="Request timeout in seconds"
    )
    follow_redirects: bool = Field(
        default=True,
        description="Whether to follow HTTP redirects"
    )
    verify_ssl: bool = Field(
        default=True,
        description="Whether to verify SSL certificates"
    )


# =============================================================================
# TOOLS
# =============================================================================

@tool(args_schema=HttpCheckInput)
def http_check(
        url: str,
        method: str = "GET",
        timeout: int = 10,
        follow_redirects: bool = True,
        verify_ssl: bool = True,
) -> str:
    """
    Check if an HTTP/HTTPS endpoint is accessible.
    Use this to verify ingress connectivity, health endpoints, or API availability.

    Returns status code, response time, and any errors encountered.
    """
    try:
        logger.info(f"Checking HTTP endpoint: {method} {url}")

        response = requests.request(
            method=method.upper(),
            url=url,
            timeout=timeout,
            allow_redirects=follow_redirects,
            verify=verify_ssl,
        )

        # Calculate response time
        elapsed_ms = response.elapsed.total_seconds() * 1000

        lines = [f"HTTP Check: {method.upper()} {url}\n"]
        lines.append(f"Status: {response.status_code} {response.reason}")
        lines.append(f"Response Time: {elapsed_ms:.0f}ms")

        # Show final URL if redirected
        if response.history:
            lines.append(f"Redirects: {len(response.history)}")
            lines.append(f"Final URL: {response.url}")

        # Show relevant headers
        lines.append("\nHeaders:")
        relevant_headers = [
            "content-type",
            "server",
            "x-powered-by",
            "content-length",
        ]
        for header in relevant_headers:
            if header in response.headers:
                lines.append(f"  {header}: {response.headers[header]}")

        # Status interpretation
        lines.append("")
        if 200 <= response.status_code < 300:
            lines.append("Result: OK - Endpoint is accessible")
        elif 300 <= response.status_code < 400:
            lines.append("Result: REDIRECT - Endpoint redirects")
        elif 400 <= response.status_code < 500:
            lines.append(f"Result: CLIENT ERROR - {response.status_code}")
        elif 500 <= response.status_code < 600:
            lines.append(f"Result: SERVER ERROR - {response.status_code}")

        logger.info(f"HTTP check completed: {response.status_code}")
        return "\n".join(lines)

    except requests.exceptions.Timeout:
        logger.warning(f"HTTP check timeout: {url}")
        return f"HTTP Check: {method.upper()} {url}\n\nResult: TIMEOUT - Request timed out after {timeout}s"

    except requests.exceptions.SSLError as e:
        logger.warning(f"HTTP check SSL error: {url} - {e}")
        return f"HTTP Check: {method.upper()} {url}\n\nResult: SSL ERROR - {e}\n\nTip: Use verify_ssl=False to skip SSL verification"

    except requests.exceptions.ConnectionError as e:
        logger.warning(f"HTTP check connection error: {url} - {e}")
        return f"HTTP Check: {method.upper()} {url}\n\nResult: CONNECTION ERROR - Could not connect to host\n\nDetails: {e}"

    except RequestException as e:
        logger.error(f"HTTP check failed: {url} - {e}")
        return f"HTTP Check: {method.upper()} {url}\n\nResult: ERROR - {e}"

    except Exception as e:
        logger.error(f"HTTP check unexpected error: {url} - {e}", exc_info=True)
        return f"Error checking HTTP endpoint: {e}"


# =============================================================================
# TOOL COLLECTION (for easy import)
# =============================================================================

network_tools = [
    http_check,
]
