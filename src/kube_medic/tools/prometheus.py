"""
Prometheus Metrics Tools.

This module provides tools for querying Prometheus:
- prometheus_query: Execute raw PromQL queries
- prometheus_query_range: Execute raw PromQL range queries for trend analysis
- get_pod_cpu_memory: Get CPU and memory usage for pods
- get_pod_restarts: Get pod restart counts
- get_cluster_health: Get overall cluster health
"""

from datetime import datetime

from langchain_core.tools import tool
from prometheus_api_client import PrometheusConnect
from pydantic import BaseModel, Field

from kube_medic.config import get_settings
from kube_medic.logging_config import get_logger
from kube_medic.utils.helpers import parse_relative_time

logger = get_logger(__name__)

# =============================================================================
# PROMETHEUS CLIENT (Singleton)
# =============================================================================

_prom_client: PrometheusConnect | None = None


def get_prometheus_client() -> PrometheusConnect:
    """Get or create the Prometheus client (singleton)."""
    global _prom_client

    if _prom_client is not None:
        return _prom_client

    settings = get_settings()
    logger.info(f"Connecting to Prometheus at {settings.prometheus_url}")

    _prom_client = PrometheusConnect(
        url=settings.prometheus_url,
        disable_ssl=True,
    )

    return _prom_client


def query_prometheus(promql: str) -> dict:
    """
    Execute a PromQL query against Prometheus.

    Args:
        promql: The PromQL query string

    Returns:
        Dict containing the Prometheus API response
    """
    logger.debug(f"Querying Prometheus: {promql[:60]}...")

    try:
        prom = get_prometheus_client()
        result = prom.custom_query(query=promql)

        logger.debug(f"Query returned {len(result)} results")
        return {"status": "success", "data": {"result": result}}

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


class PodMetricsInput(BaseModel):
    """Input schema for pod metrics queries."""

    namespace: str = Field(
        default="",
        description="Namespace to filter (empty for all)"
    )
    pod_name: str = Field(
        default="",
        description="Specific pod name (empty for all)"
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
    logger.debug(f"Range query: {query[:60]}... from {start} to {end}, step {step}")

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


@tool(args_schema=PodMetricsInput)
def get_pod_cpu_memory(namespace: str = "", pod_name: str = "") -> str:
    """
    Get current CPU and memory usage for pods.
    Use this to find resource-hungry or throttled pods.
    """
    # Build label filter
    label_filter = ""
    if namespace:
        label_filter += f', namespace="{namespace}"'
    if pod_name:
        label_filter += f', pod=~".*{pod_name}.*"'

    # CPU query (rate over 5 minutes)
    cpu_query = f'sum(rate(container_cpu_usage_seconds_total{{container!=""{label_filter}}}[5m])) by (namespace, pod)'

    # Memory query (current usage in MB)
    mem_query = f'sum(container_memory_usage_bytes{{container!=""{label_filter}}}) by (namespace, pod) / 1024 / 1024'

    cpu_result = query_prometheus(cpu_query)
    mem_result = query_prometheus(mem_query)

    # Combine results
    pod_metrics: dict[str, dict[str, float]] = {}

    if cpu_result.get("status") == "success":
        for r in cpu_result.get("data", {}).get("result", []):
            key = f"{r['metric'].get('namespace', 'unknown')}/{r['metric'].get('pod', 'unknown')}"
            pod_metrics[key] = {"cpu_cores": float(r["value"][1])}

    if mem_result.get("status") == "success":
        for r in mem_result.get("data", {}).get("result", []):
            key = f"{r['metric'].get('namespace', 'unknown')}/{r['metric'].get('pod', 'unknown')}"
            if key in pod_metrics:
                pod_metrics[key]["memory_mb"] = float(r["value"][1])
            else:
                pod_metrics[key] = {"memory_mb": float(r["value"][1])}

    if not pod_metrics:
        return "No CPU/memory metrics found. Metrics may not be available yet."

    # Sort by CPU usage (descending)
    sorted_pods = sorted(
        pod_metrics.items(),
        key=lambda x: x[1].get("cpu_cores", 0),
        reverse=True
    )

    lines = [f"Pod Resource Usage (top {min(15, len(sorted_pods))}):\n"]
    lines.append(f"{'POD':<60} {'CPU (cores)':<12} {'MEMORY (MB)':<12}")
    lines.append("-" * 84)

    for pod, metrics in sorted_pods[:15]:
        cpu = metrics.get("cpu_cores", 0)
        mem = metrics.get("memory_mb", 0)
        lines.append(f"{pod:<60} {cpu:<12.3f} {mem:<12.1f}")

    return "\n".join(lines)


@tool(args_schema=PodMetricsInput)
def get_pod_restarts(namespace: str = "", pod_name: str = "") -> str:
    """
    Get pod restart counts from Prometheus.
    Use this to find unstable pods that keep crashing.
    """
    label_filter = ""
    if namespace:
        label_filter += f', namespace="{namespace}"'
    if pod_name:
        label_filter += f', pod=~".*{pod_name}.*"'

    query = f'sum(kube_pod_container_status_restarts_total{{container!=""{label_filter}}}) by (namespace, pod)'

    result = query_prometheus(query)

    if result.get("status") == "error":
        return f"Error querying restarts: {result.get('error')}"

    results = result.get("data", {}).get("result", [])

    if not results:
        return "No restart data found."

    # Filter and sort by restart count
    pods_with_restarts = []
    for r in results:
        restarts = int(float(r["value"][1]))
        if restarts > 0:
            pods_with_restarts.append({
                "namespace": r["metric"].get("namespace", "unknown"),
                "pod": r["metric"].get("pod", "unknown"),
                "restarts": restarts
            })

    pods_with_restarts.sort(key=lambda x: x["restarts"], reverse=True)

    if not pods_with_restarts:
        return "No pods with restarts found. All pods are stable."

    lines = [f"Pods with Restarts ({len(pods_with_restarts)} total):\n"]
    for p in pods_with_restarts[:20]:
        lines.append(f"  ⚠️  {p['namespace']}/{p['pod']}: {p['restarts']} restarts")

    return "\n".join(lines)


@tool
def get_cluster_health() -> str:
    """
    Get overall cluster health metrics from Prometheus.
    Use this for a quick health overview.
    """
    metrics: dict = {}

    # Total pods by status
    pod_status = query_prometheus('sum(kube_pod_status_phase) by (phase)')
    if pod_status.get("status") == "success":
        metrics["pod_status"] = {
            r["metric"].get("phase", "unknown"): int(float(r["value"][1]))
            for r in pod_status.get("data", {}).get("result", [])
        }

    # Pods with high restart counts
    high_restarts = query_prometheus('count(kube_pod_container_status_restarts_total > 5)')
    if high_restarts.get("status") == "success":
        results = high_restarts.get("data", {}).get("result", [])
        metrics["pods_high_restarts"] = int(float(results[0]["value"][1])) if results else 0

    # Node status
    node_status = query_prometheus(
        'sum(kube_node_status_condition{condition="Ready",status="true"})'
    )
    if node_status.get("status") == "success":
        results = node_status.get("data", {}).get("result", [])
        metrics["nodes_ready"] = int(float(results[0]["value"][1])) if results else 0

    # Format output
    lines = ["Cluster Health Summary:\n"]

    if "pod_status" in metrics:
        lines.append("Pod Status:")
        for phase, count in metrics["pod_status"].items():
            emoji = "✅" if phase == "Running" else "⚠️" if phase == "Pending" else "❌"
            lines.append(f"  {emoji} {phase}: {count}")

    if "pods_high_restarts" in metrics:
        count = metrics["pods_high_restarts"]
        emoji = "✅" if count == 0 else "⚠️"
        lines.append(f"\n{emoji} Pods with >5 restarts: {count}")

    if "nodes_ready" in metrics:
        lines.append(f"✅ Nodes ready: {metrics['nodes_ready']}")

    return "\n".join(lines)


# =============================================================================
# TOOL COLLECTION (for easy import)
# =============================================================================

prometheus_tools = [
    prometheus_query,
    prometheus_query_range,
    get_pod_cpu_memory,
    get_pod_restarts,
    get_cluster_health,
]
