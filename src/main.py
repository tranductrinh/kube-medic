import os
import time

import requests
from dotenv import load_dotenv
from kubernetes import config, client
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import AzureChatOpenAI
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()

# Monitoring service endpoints
if not os.environ.get("PROMETHEUS_URL"):
    print("PROMETHEUS_URL not set!")
    exit(1)
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL")
print(f"Prometheus URL: {PROMETHEUS_URL}")

# Load Kubernetes configuration
try:
    config.load_kube_config()
except config.ConfigException:
    try:
        config.load_incluster_config()
    except config.ConfigException:
        print("Could not load Kubernetes config!")
        exit(1)

# Kubernetes tools
v1 = client.CoreV1Api()


class ListPodsInput(BaseModel):
    """Input schema for listing pods."""
    namespace: str = Field(
        default="",0
        description="Kubernetes namespace. Leave empty for all namespaces."
    )
    label_selector: str = Field(
        default="",
        description="Label selector to filter pods (e.g., 'app=nginx')"
    )


class GetPodDetailsInput(BaseModel):
    """Input schema for getting pod details."""
    pod_name: str = Field(
        ...,  # Required
        description="Name of the pod to get details for"
    )
    namespace: str = Field(
        default="default",
        description="Namespace where the pod is located"
    )


class GetPodLogsInput(BaseModel):
    """Input schema for getting pod logs."""
    pod_name: str = Field(..., description="Name of the pod")
    namespace: str = Field(default="default", description="Namespace of the pod")
    container: str = Field(
        default="",
        description="Container name (required if pod has multiple containers)"
    )
    tail_lines: int = Field(
        default=50,
        description="Number of log lines to retrieve from the end"
    )


class GetEventsInput(BaseModel):
    """Input schema for getting Kubernetes events."""
    namespace: str = Field(
        default="",
        description="Namespace to get events from. Empty for all namespaces."
    )
    resource_name: str = Field(
        default="",
        description="Filter events for a specific resource (e.g., pod name)"
    )


@tool(args_schema=ListPodsInput)
def list_pods(namespace: str = "", label_selector: str = "") -> str:
    """
    List pods in the Kubernetes cluster.
    Use this tool to see what pods exist and their status.

    Returns a summary of pods including name, namespace, status, and restarts.
    """

    try:
        if namespace:
            pods = v1.list_namespaced_pod(
                namespace=namespace,
                label_selector=label_selector or None
            )
        else:
            pods = v1.list_pod_for_all_namespaces(
                label_selector=label_selector or None
            )

        if not pods.items:
            return "No pods found."

        lines = [f"Found {len(pods.items)} pods:\n"]

        for pod in pods.items:
            restarts = 0

            if pod.status.container_statuses:
                restarts = sum(cs.restart_count for cs in pod.status.container_statuses)

            status = pod.status.phase
            if pod.status.container_statuses:
                for cs in pod.status.container_statuses:
                    if cs.state.waiting:
                        status = cs.state.waiting.reason
                    elif cs.state.terminated:
                        status = cs.state.terminated.reason

            lines.append(
                f"  - {pod.metadata.namespace}/{pod.metadata.name}: "
                f"{status} (restarts: {restarts})"
            )

        return "\n".join(lines)

    except Exception as e:
        return f"Error listing pods: {str(e)}"


@tool(args_schema=GetPodDetailsInput)
def get_pod_details(pod_name: str, namespace: str = "default") -> str:
    """
    Get detailed information about a specific pod.
    Use this to investigate pod configuration, container status, and issues.

    Returns pod status, container details, resource limits, and conditions.
    """
    try:
        pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)

        # Build detailed response
        lines = [f"Pod: {namespace}/{pod_name}"]
        lines.append(f"Status: {pod.status.phase}")
        lines.append(f"Node: {pod.spec.node_name}")
        lines.append(f"IP: {pod.status.pod_ip}")

        # Container statuses
        lines.append("\nContainers:")
        if pod.status.container_statuses:
            for cs in pod.status.container_statuses:
                state = "Unknown"
                if cs.state.running:
                    state = "Running"
                elif cs.state.waiting:
                    state = f"Waiting ({cs.state.waiting.reason})"
                elif cs.state.terminated:
                    state = f"Terminated ({cs.state.terminated.reason})"

                lines.append(
                    f"  - {cs.name}: {state}, Ready: {cs.ready}, "
                    f"Restarts: {cs.restart_count}"
                )

        # Conditions
        lines.append("\nConditions:")
        if pod.status.conditions:
            for cond in pod.status.conditions:
                lines.append(
                    f"  - {cond.type}: {cond.status}"
                    + (f" ({cond.reason})" if cond.reason else "")
                )

        # Labels
        if pod.metadata.labels:
            lines.append(f"\nLabels: {pod.metadata.labels}")

        return "\n".join(lines)

    except client.ApiException as e:
        if e.status == 404:
            return f"Pod '{pod_name}' not found in namespace '{namespace}'"
        return f"Error getting pod details: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"


@tool(args_schema=GetPodLogsInput)
def get_pod_logs(
        pod_name: str,
        namespace: str = "default",
        container: str = "",
        tail_lines: int = 50
) -> str:
    """
    Get logs from a Kubernetes pod.
    Use this to investigate application errors, crashes, or behavior.

    Returns the last N lines of logs from the specified pod/container.
    """
    try:
        kwargs = {
            "name": pod_name,
            "namespace": namespace,
            "tail_lines": tail_lines,
        }
        if container:
            kwargs["container"] = container

        logs = v1.read_namespaced_pod_log(**kwargs)

        if not logs:
            return f"No logs found for pod {pod_name}"

        # Truncate if too long (LLM context limits)
        max_chars = 3000
        if len(logs) > max_chars:
            logs = f"[...truncated...]\n{logs[-max_chars:]}"

        return f"Logs from {namespace}/{pod_name} (last {tail_lines} lines):\n\n{logs}"

    except client.ApiException as e:
        if e.status == 404:
            return f"Pod '{pod_name}' not found in namespace '{namespace}'"
        return f"Error getting logs: {e.reason}"
    except Exception as e:
        return f"Error: {str(e)}"


@tool(args_schema=GetEventsInput)
def get_events(namespace: str = "", resource_name: str = "") -> str:
    """
    Get Kubernetes events to understand what's happening in the cluster.
    Use this to find errors, warnings, and recent changes.

    Events show things like pod scheduling, image pulls, container crashes, etc.
    """
    try:
        if namespace:
            events = v1.list_namespaced_event(namespace=namespace)
        else:
            events = v1.list_event_for_all_namespaces()

        # Filter by resource name if specified
        if resource_name:
            events.items = [
                e for e in events.items
                if e.involved_object.name == resource_name
            ]

        # Sort by last timestamp (most recent first)
        events.items.sort(
            key=lambda e: e.last_timestamp or e.event_time or e.metadata.creation_timestamp,
            reverse=True
        )

        # Take last 20 events
        events.items = events.items[:20]

        if not events.items:
            return "No events found."

        lines = [f"Found {len(events.items)} events (most recent first):\n"]

        for event in events.items:
            timestamp = event.last_timestamp or event.event_time
            lines.append(
                f"  [{event.type}] {event.involved_object.kind}/{event.involved_object.name}\n"
                f"    Reason: {event.reason}\n"
                f"    Message: {event.message}\n"
                f"    Count: {event.count}, Last: {timestamp}"
            )

        return "\n".join(lines)

    except Exception as e:
        return f"Error getting events: {str(e)}"


@tool
def list_namespaces() -> str:
    """
    List all namespaces in the Kubernetes cluster.
    Use this to understand the structure of the cluster.
    """
    try:
        namespaces = v1.list_namespace()
        lines = [f"Found {len(namespaces.items)} namespaces:\n"]

        for ns in namespaces.items:
            status = ns.status.phase
            lines.append(f"  - {ns.metadata.name}: {status}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error listing namespaces: {str(e)}"


# Create an LLM model
if not os.environ.get("AZURE_OPENAI_ENDPOINT"):
    print("AZURE_OPENAI_ENDPOINT not set!")
    exit(1)
if not os.environ.get("AZURE_OPENAI_API_KEY"):
    print("AZURE_OPENAI_API_KEY not set!")
    exit(1)
if not os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME"):
    print("AZURE_OPENAI_DEPLOYMENT_NAME not set!")
    exit(1)

llm = AzureChatOpenAI(
    azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
    api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
    azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME"),
    api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
    temperature=0,
    max_tokens=2048,
)


# Prometheus tools
def query_prometheus(promql: str, time: str = None) -> dict:
    """Execute a PromQL query against Prometheus."""
    params = {"query": promql}
    if time:
        params["time"] = time

    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params=params,
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"status": "error", "error": str(e)}


class PrometheusQueryInput(BaseModel):
    query: str = Field(..., description="PromQL query to execute")


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

    for r in results[:20]:  # Limit to 20 results
        metric = r.get("metric", {})
        value = r.get("value", [None, None])

        # Format metric labels
        labels = ", ".join(f'{k}="{v}"' for k, v in metric.items() if k != "__name__")
        metric_name = metric.get("__name__", "unknown")

        lines.append(f"  {metric_name}{{{labels}}}: {value[1]}")

    if len(results) > 20:
        lines.append(f"  ... and {len(results) - 20} more results")

    return "\n".join(lines)


class PodMetricsInput(BaseModel):
    namespace: str = Field(default="", description="Namespace to filter (empty for all)")
    pod_name: str = Field(default="", description="Specific pod name (empty for all)")


@tool(args_schema=PodMetricsInput)
def get_pod_cpu_memory(namespace: str = "", pod_name: str = "") -> str:
    """
    Get current CPU and memory usage for pods.
    Use this to find resource-hungry or throttled pods.
    """
    # Build label selector
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
    pod_metrics = {}

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
    sorted_pods = sorted(pod_metrics.items(), key=lambda x: x[1].get("cpu_cores", 0), reverse=True)

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
    metrics = {}

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
    node_status = query_prometheus('sum(kube_node_status_condition{condition="Ready",status="true"})')
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


# ALL tools
tools = [
    # Kubernetes
    list_namespaces,
    list_pods,
    get_pod_details,
    get_pod_logs,
    get_events,
    # Prometheus
    prometheus_query,
    get_pod_cpu_memory,
    get_pod_restarts,
    get_cluster_health,
]

# Enhanced system prompt with troubleshooting methodology
system_prompt = """You are an expert Kubernetes troubleshooting assistant with access to:
- Kubernetes API (namespaces, pods, pod logs, events)
- Prometheus metrics (CPU, memory, restarts)

TROUBLESHOOTING METHODOLOGY:

1. UNDERSTAND the problem
   - What is the user asking about?
   - Which namespace/pods are affected?

2. GATHER data systematically
   - Start with get_cluster_health for overview
   - Check pod status with list_pods
   - Look at events with get_events
   - Check pod details with get_pod_details
   - Get pod logs with get_pod_logs
   - Check metrics with get_pod_cpu_memory or get_pod_restarts

3. ANALYZE the data
   - Correlate events, metrics, and logs
   - Identify patterns (high restarts, memory spikes, error messages)
   - Consider common root causes

4. REPORT findings clearly
   - Summarize what you found
   - Identify the likely root cause
   - Recommend specific actions (but NEVER auto-fix)

COMMON TROUBLESHOOTING SCENARIOS:

- Pod CrashLoopBackOff → Check logs for startup errors, check memory limits
- Pod Pending → Check events for scheduling issues, node resources
- High latency → Check CPU/memory metrics, look for throttling
- Application errors → Search logs for exceptions, check dependencies

RULES:
- Always use tools to get real data
- Be systematic - don't jump to conclusions
- Highlight critical findings (errors, high restarts, resource issues)
- Provide actionable recommendations"""

# Create the agent
agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt=system_prompt,
)


def ask_agent(query: str) -> str:
    """Run a query and stream the message flow."""
    final_response = ""

    for step in agent.stream(
            {"messages": [{"role": "user", "content": query}]}
    ):
        for update in step.values():
            for message in update.get("messages", []):
                message.pretty_print()

                # Capture the final AI response
                if hasattr(message, 'content') and message.content:
                    if hasattr(message, 'type') and message.type == 'ai':
                        if not (hasattr(message, 'tool_calls') and message.tool_calls):
                            final_response = message.content

    return final_response


# Test queries that use the new observability tools
test_queries = [
    "Give me a quick health check of the cluster",
    "Are there any pods with high restart counts?",
    "Check for any errors in the logging-system namespace",
]

# Only run tests if we have connectivity
print("\nRunning test queries...\n")

for query in test_queries:
    try:
        ask_agent(query)
    except Exception as e:
        print(f"Error running query: {e}")
    time.sleep(1)
