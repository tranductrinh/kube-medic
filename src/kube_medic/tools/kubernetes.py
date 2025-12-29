"""
Kubernetes API Tools.

This module provides tools for interacting with the Kubernetes API:
- list_namespaces: List cluster namespaces
- list_pods: List pods with status
- get_pod_details: Get detailed pod information
- get_pod_logs: Retrieve pod logs
- get_events: Get Kubernetes events
"""

import logging

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from kube_medic.config import get_settings

logger = logging.getLogger(__name__)


# =============================================================================
# KUBERNETES CLIENT (Singleton Pattern)
# =============================================================================

_v1_client: client.CoreV1Api | None = None


def get_k8s_client() -> client.CoreV1Api:
    """
    Get or create the Kubernetes API client.

    Uses singleton pattern - only creates client once.
    """
    global _v1_client

    if _v1_client is not None:
        logger.debug("Reusing existing Kubernetes API client")
        return _v1_client

    logger.info("Initializing Kubernetes API client...")

    # Try kubeconfig first (local development)
    try:
        config.load_kube_config()
        logger.info("Loaded kubeconfig from local filesystem")
    except config.ConfigException:
        # Fall back to in-cluster config (running in K8s)
        try:
            config.load_incluster_config()
            logger.info("Loaded in-cluster Kubernetes configuration")
        except config.ConfigException as e:
            logger.error("Could not load Kubernetes configuration")
            raise RuntimeError("Could not load Kubernetes configuration") from e

    _v1_client = client.CoreV1Api()
    logger.info("Kubernetes API client initialized successfully")
    return _v1_client


# =============================================================================
# INPUT SCHEMAS
# =============================================================================

class ListPodsInput(BaseModel):
    """Input schema for listing pods."""

    namespace: str = Field(
        default="",
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
        default=None,
        description="Number of log lines to retrieve from the end (uses config default if not specified)"
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


# =============================================================================
# TOOLS
# =============================================================================

@tool
def list_namespaces() -> str:
    """
    List all namespaces in the Kubernetes cluster.
    Use this to understand the structure of the cluster.
    """
    try:
        logger.info("Listing namespaces...")
        v1 = get_k8s_client()
        namespaces = v1.list_namespace()

        if not namespaces.items:
            logger.warning("No namespaces found in cluster")
            return "No namespaces found."

        logger.info(f"Found {len(namespaces.items)} namespaces")
        lines = [f"Found {len(namespaces.items)} namespaces:\n"]
        for ns in namespaces.items:
            status = ns.status.phase
            lines.append(f"  - {ns.metadata.name}: {status}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error listing namespaces: {e}", exc_info=True)
        return f"Error listing namespaces: {e}"


@tool(args_schema=ListPodsInput)
def list_pods(namespace: str = "", label_selector: str = "") -> str:
    """
    List pods in the Kubernetes cluster.
    Use this tool to see what pods exist and their status.

    Returns a summary of pods including name, namespace, status, and restarts.
    """
    try:
        logger.info(f"Listing pods (namespace={namespace or 'all'}, selector={label_selector or 'none'})")
        v1 = get_k8s_client()

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
            logger.warning("No pods found")
            return "No pods found."

        logger.info(f"Found {len(pods.items)} pods")
        lines = [f"Found {len(pods.items)} pods:\n"]

        for pod in pods.items:
            restarts = 0
            status = pod.status.phase

            if pod.status.container_statuses:
                restarts = sum(cs.restart_count for cs in pod.status.container_statuses)
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
        return f"Error listing pods: {e}"


@tool(args_schema=GetPodDetailsInput)
def get_pod_details(pod_name: str, namespace: str = "default") -> str:
    """
    Get detailed information about a specific pod.
    Use this to investigate pod configuration, container status, and issues.

    Returns pod status, container details, resource limits, and conditions.
    """
    try:
        v1 = get_k8s_client()
        pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)

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

    except ApiException as e:
        if e.status == 404:
            return f"Pod '{pod_name}' not found in namespace '{namespace}'"
        return f"Error getting pod details: {e}"
    except Exception as e:
        return f"Error: {e}"


@tool(args_schema=GetPodLogsInput)
def get_pod_logs(
        pod_name: str,
        namespace: str = "default",
        container: str = "",
        tail_lines: int = None
) -> str:
    """
    Get logs from a Kubernetes pod.
    Use this to investigate application errors, crashes, or behavior.

    Returns the last N lines of logs from the specified pod/container.
    """
    try:
        logger.info(f"Getting logs for pod {namespace}/{pod_name}")
        settings = get_settings()

        # Use config default if not specified
        if tail_lines is None:
            tail_lines = settings.k8s_logs_tail_lines

        logger.debug(f"Tail lines: {tail_lines}, container: {container or 'default'}")

        v1 = get_k8s_client()

        kwargs = {
            "name": pod_name,
            "namespace": namespace,
            "tail_lines": tail_lines,
        }
        if container:
            kwargs["container"] = container

        logs = v1.read_namespaced_pod_log(**kwargs)

        if not logs:
            logger.warning(f"No logs found for {namespace}/{pod_name}")
            return f"No logs found for pod {pod_name}"

        logger.info(f"Retrieved {len(logs)} characters of logs")

        # Truncate if too long (LLM context limits)
        max_chars = settings.k8s_logs_max_chars
        if len(logs) > max_chars:
            logger.debug(f"Truncating logs from {len(logs)} to {max_chars} chars")
            logs = f"[...truncated...]\n{logs[-max_chars:]}"

        return f"Logs from {namespace}/{pod_name} (last {tail_lines} lines):\n\n{logs}"

    except ApiException as e:
        if e.status == 404:
            logger.warning(f"Pod '{pod_name}' not found in namespace '{namespace}'")
            return f"Pod '{pod_name}' not found in namespace '{namespace}'"
        logger.error(f"API error getting logs: {e}", exc_info=True)
        return f"Error getting logs: {e.reason}"
    except Exception as e:
        logger.error(f"Error getting pod logs: {e}", exc_info=True)
        return f"Error: {e}"
    except Exception as e:
        return f"Error: {e}"


@tool(args_schema=GetEventsInput)
def get_events(namespace: str = "", resource_name: str = "") -> str:
    """
    Get Kubernetes events to understand what's happening in the cluster.
    Use this to find errors, warnings, and recent changes.

    Events show things like pod scheduling, image pulls, container crashes, etc.
    """
    try:
        v1 = get_k8s_client()

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

        # Sort by timestamp (most recent first)
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
        return f"Error getting events: {e}"


# =============================================================================
# TOOL COLLECTION (for easy import)
# =============================================================================

kubernetes_tools = [
    list_namespaces,
    list_pods,
    get_pod_details,
    get_pod_logs,
    get_events,
]