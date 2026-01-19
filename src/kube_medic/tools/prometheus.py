"""
Prometheus Metrics Tools.

This module provides tools for querying Prometheus:
- prometheus_query: Execute PromQL queries
- prometheus_query_range: Execute PromQL range queries for trend analysis

Features:
- Query result caching with configurable TTL
- Query validation for safety (prevents expensive/dangerous queries)
"""

import base64
import re
from datetime import datetime
from threading import Lock

from cachetools import TTLCache
from langchain_core.tools import tool
from prometheus_api_client import PrometheusConnect
from pydantic import BaseModel, Field

from kube_medic.config import get_settings
from kube_medic.logging_config import get_logger
from kube_medic.utils.helpers import parse_relative_time

logger = get_logger(__name__)


# =============================================================================
# QUERY CACHE
# =============================================================================

_query_cache: TTLCache | None = None
_cache_lock = Lock()


def _get_query_cache() -> TTLCache:
    """Get or create the query cache with settings from config."""
    global _query_cache
    if _query_cache is None:
        settings = get_settings()
        _query_cache = TTLCache(
            maxsize=settings.cache_prometheus_maxsize,
            ttl=settings.cache_prometheus_ttl,
        )
        logger.info(
            f"Prometheus query cache initialized "
            f"(maxsize={settings.cache_prometheus_maxsize}, ttl={settings.cache_prometheus_ttl}s)"
        )
    return _query_cache


# =============================================================================
# QUERY VALIDATION
# =============================================================================

class PromQLValidationError(Exception):
    """Raised when PromQL query fails validation."""
    pass


def _validate_promql(query: str) -> None:
    """
    Validate PromQL query for safety.

    Checks for:
    - Maximum query length
    - Dangerous patterns that could impact Prometheus performance
    - Excessive nesting depth

    Raises:
        PromQLValidationError: If query is potentially dangerous
    """
    # Max query length
    if len(query) > 2000:
        raise PromQLValidationError(
            f"Query exceeds maximum length (2000 chars). Length: {len(query)}"
        )

    # Check for dangerous patterns
    dangerous_patterns = [
        # Very long label matchers (could indicate injection or expensive queries)
        (r'\{[^}]{500,}\}', "Label matcher too long (>500 chars)"),
        # Many range vectors in single query (expensive)
        (r'(\[[^\]]+\].*){5,}', "Too many range vectors (>5)"),
        # Many set operations chained together
        (r'((?:^|\s)(?:or|and|unless)(?:\s|$).*){4,}', "Too many set operations (>4)"),
    ]

    for pattern, message in dangerous_patterns:
        if re.search(pattern, query, re.IGNORECASE):
            logger.warning(f"PromQL validation failed: {message}")
            raise PromQLValidationError(f"Query validation failed: {message}")

    # Check nested function depth (rough heuristic)
    open_parens = 0
    max_depth = 0
    for char in query:
        if char == '(':
            open_parens += 1
            max_depth = max(max_depth, open_parens)
        elif char == ')':
            open_parens -= 1

    if max_depth > 10:
        logger.warning(f"PromQL validation failed: Query too deeply nested (depth: {max_depth})")
        raise PromQLValidationError(
            f"Query too deeply nested (depth: {max_depth}, max: 10)"
        )

    logger.debug(f"PromQL validation passed (length: {len(query)}, depth: {max_depth})")

# =============================================================================
# PROMETHEUS CLIENT (Singleton)
# =============================================================================

_prom_client: PrometheusConnect | None = None


def get_prometheus_client() -> PrometheusConnect:
    """Get or create the Prometheus client (singleton)."""
    global _prom_client

    if _prom_client is not None:
        logger.debug("Reusing existing Prometheus client")
        return _prom_client

    settings = get_settings()
    logger.info(f"Initializing Prometheus client for {settings.prometheus_url}")

    # Build headers with basic auth if credentials are provided
    headers: dict[str, str] = {}
    if settings.prometheus_username and settings.prometheus_password:
        credentials = f"{settings.prometheus_username}:{settings.prometheus_password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        headers["Authorization"] = f"Basic {encoded}"
        logger.debug("Using basic authentication for Prometheus")

    _prom_client = PrometheusConnect(
        url=settings.prometheus_url,
        headers=headers if headers else None,
        disable_ssl=True,
    )

    return _prom_client


def _sanitize_promql(query: str) -> str:
    """
    Sanitize a PromQL query by removing invalid escape sequences.

    LLMs sometimes escape dots (\\.) in metric names, but PromQL doesn't use
    backslash escaping - dots are literal characters.
    """
    original = query
    # Remove any backslashes before dots (common LLM mistake)
    # This handles \. , \\. , \\\. etc.
    sanitized = re.sub(r'\\+\.', '.', query)

    if sanitized != original:
        logger.warning(f"Sanitized PromQL: removed backslash escapes from query")
        logger.debug(f"Original: {original[:100]}")
        logger.debug(f"Sanitized: {sanitized[:100]}")
    return sanitized


def query_prometheus(promql: str, use_cache: bool = True) -> dict:
    """
    Execute a PromQL query against Prometheus with caching and validation.

    Args:
        promql: The PromQL query string
        use_cache: Whether to use cached results (default: True)

    Returns:
        Dict containing the Prometheus API response
    """
    # Sanitize query to fix common LLM mistakes
    promql = _sanitize_promql(promql)
    logger.debug(f"Querying Prometheus: {promql[:100]}...")

    # Validate query for safety
    try:
        _validate_promql(promql)
    except PromQLValidationError as e:
        logger.warning(f"Query validation failed: {e}")
        return {"status": "error", "error": str(e)}

    # Check cache first
    cache_key = f"prom_instant:{promql}"
    if use_cache:
        cache = _get_query_cache()
        with _cache_lock:
            if cache_key in cache:
                logger.debug(f"Cache hit for query: {promql[:50]}...")
                return cache[cache_key]

    try:
        prom = get_prometheus_client()
        result = prom.custom_query(query=promql)

        logger.debug(f"Query returned {len(result)} results")
        response = {"status": "success", "data": {"result": result}}

        # Cache the result
        if use_cache:
            with _cache_lock:
                _get_query_cache()[cache_key] = response
                logger.debug(f"Cached query result (cache size: {len(_get_query_cache())})")

        return response

    except Exception as e:
        logger.error(f"Prometheus query failed: {e}")
        return {"status": "error", "error": str(e)}


# =============================================================================
# INPUT SCHEMAS
# =============================================================================

class PrometheusQueryInput(BaseModel):
    """Input schema for Prometheus queries."""

    query: str = Field(..., description="PromQL query to execute")


class PrometheusRangeQueryInput(BaseModel):
    """Input schema for Prometheus range queries."""
    query: str = Field(..., description="PromQL query to execute")
    start: str = Field(
        default="1h",
        description="Start time (e.g., '1h' for 1 hour ago, '30m' for 30 minutes ago, or ISO timestamp)"
    )
    end: str = Field(
        default="now",
        description="End time (e.g., 'now' or ISO timestamp)"
    )
    step: str = Field(
        default="1m",
        description="Query resolution step (e.g., '15s', '1m', '5m')"
    )


# =============================================================================
# TOOLS
# =============================================================================

@tool(args_schema=PrometheusQueryInput)
def prometheus_query(query: str) -> str:
    """
    Execute a raw PromQL query against Prometheus.
    Use this for custom metrics queries.

    Example queries:
    - up{job="kubernetes-pods"}
    - rate(container_cpu_usage_seconds_total[5m])
    - kube_pod_container_status_restarts_total
    """
    result = query_prometheus(query)

    if result.get("status") == "error":
        return f"Prometheus error: {result.get('error', 'Unknown error')}"

    data = result.get("data", {})
    results = data.get("result", [])

    if not results:
        return "No data returned for this query."

    lines = [f"Query: {query}\nResults ({len(results)} series):\n"]

    settings = get_settings()
    max_results = settings.prometheus_max_series_results
    for r in results[:max_results]:
        metric = r.get("metric", {})
        value = r.get("value", [None, None])

        # Format metric labels
        labels = ", ".join(f'{k}="{v}"' for k, v in metric.items() if k != "__name__")
        metric_name = metric.get("__name__", "unknown")

        lines.append(f"  {metric_name}{{{labels}}}: {value[1]}")

    if len(results) > max_results:
        lines.append(f"  ... and {len(results) - max_results} more results")

    return "\n".join(lines)


@tool(args_schema=PrometheusRangeQueryInput)
def prometheus_query_range(
        query: str,
        start: str = "1h",
        end: str = "now",
        step: str = "1m"
) -> str:
    """
    Execute a PromQL range query against Prometheus.
    Use this to get metrics over a time period for trend analysis.

    Examples:
    - Query CPU over last hour: query="rate(container_cpu_usage_seconds_total[5m])", start="1h"
    - Query memory over last day: query="container_memory_usage_bytes", start="1d", step="5m"
    """
    # Sanitize query to fix common LLM mistakes
    query = _sanitize_promql(query)
    logger.debug(f"Range query: {query[:100]}... from {start} to {end}, step {step}")

    # Validate query for safety
    try:
        _validate_promql(query)
    except PromQLValidationError as e:
        return f"Query validation failed: {e}"

    try:
        prom = get_prometheus_client()

        start_time = parse_relative_time(start)
        end_time = parse_relative_time(end)

        result = prom.custom_query_range(
            query=query,
            start_time=start_time,
            end_time=end_time,
            step=step,
        )

        if not result:
            return "No data returned for this range query."

        lines = [f"Range Query: {query}"]
        lines.append(f"Time Range: {start_time.isoformat()} to {end_time.isoformat()}")
        lines.append(f"Step: {step}")
        lines.append(f"Results ({len(result)} series):\n")

        settings = get_settings()
        max_results = settings.prometheus_max_series_results

        for r in result[:max_results]:
            metric = r.get("metric", {})
            values = r.get("values", [])

            # Format metric labels
            labels = ", ".join(f'{k}="{v}"' for k, v in metric.items() if k != "__name__")
            metric_name = metric.get("__name__", "unknown")

            lines.append(f"  {metric_name}{{{labels}}}:")
            lines.append(f"    Data points: {len(values)}")

            if values:
                # Show first, middle, and last values
                first_ts, first_val = values[0]
                last_ts, last_val = values[-1]
                lines.append(f"    First: {datetime.fromtimestamp(first_ts).isoformat()} = {first_val}")
                lines.append(f"    Last:  {datetime.fromtimestamp(last_ts).isoformat()} = {last_val}")

                # Calculate simple stats
                numeric_values = [float(v[1]) for v in values if v[1] != 'NaN']
                if numeric_values:
                    lines.append(
                        f"    Min: {min(numeric_values):.3f}, Max: {max(numeric_values):.3f}, Avg: {sum(numeric_values) / len(numeric_values):.3f}")

        if len(result) > max_results:
            lines.append(f"\n  ... and {len(result) - max_results} more series")

        return "\n".join(lines)

    except ValueError as e:
        return f"Invalid time format: {e}"
    except Exception as e:
        logger.error(f"Prometheus range query failed: {e}")
        return f"Prometheus error: {e}"


# =============================================================================
# CACHE UTILITIES
# =============================================================================

def get_prometheus_cache_stats() -> dict:
    """Get Prometheus query cache statistics for monitoring."""
    cache = _get_query_cache()
    with _cache_lock:
        settings = get_settings()
        return {
            "current_size": len(cache),
            "max_size": settings.cache_prometheus_maxsize,
            "ttl_seconds": settings.cache_prometheus_ttl,
        }


def clear_prometheus_cache() -> int:
    """Clear the Prometheus query cache. Returns number of entries cleared."""
    cache = _get_query_cache()
    with _cache_lock:
        count = len(cache)
        cache.clear()
        logger.info(f"Cleared {count} entries from Prometheus cache")
        return count


# =============================================================================
# TOOL COLLECTION (for easy import)
# =============================================================================

prometheus_tools = [
    prometheus_query,
    prometheus_query_range,
]
