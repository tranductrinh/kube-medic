"""
Kubernetes API Tools (READ-ONLY).

This module provides read-only tools for Kubernetes troubleshooting.
No create, update, or delete operations are permitted.

Tools:
- list_namespaces: List cluster namespaces
- list_pods: List pods with status
- get_pod_details: Get detailed pod information
- get_pod_logs: Retrieve pod logs
- get_events: Get Kubernetes events
- list_deployments: List deployments and replica status
- list_services: List services and endpoints
- list_ingresses: List ingresses and routing rules
- list_nodes: List cluster nodes
- get_node_details: Get node details and conditions
- list_configmaps: List ConfigMaps in a namespace
- list_secrets: List Secret names (not values)
"""

from kube_medic.config import get_settings
from kube_medic.logging_config import get_logger
from kubernetes.client.exceptions import ApiException
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from kubernetes import client, config

logger = get_logger(__name__)

# =============================================================================
# KUBERNETES CLIENT (Singleton Pattern)
# =============================================================================

_v1_client: client.CoreV1Api | None = None
_apps_client: client.AppsV1Api | None = None
_networking_client: client.NetworkingV1Api | None = None


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


def get_apps_client() -> client.AppsV1Api:
    """
    Get or create the Kubernetes AppsV1Api client for deployments.

    Uses singleton pattern - only creates client once.
    """
    global _apps_client

    if _apps_client is not None:
        return _apps_client

    # Ensure config is loaded (will be done by get_k8s_client if not already)
    get_k8s_client()

    _apps_client = client.AppsV1Api()
    logger.debug("AppsV1Api client initialized")
    return _apps_client


def get_networking_client() -> client.NetworkingV1Api:
    """
    Get or create the Kubernetes NetworkingV1Api client for ingresses.

    Uses singleton pattern - only creates client once.
    """
    global _networking_client

    if _networking_client is not None:
        return _networking_client

    # Ensure config is loaded (will be done by get_k8s_client if not already)
    get_k8s_client()

    _networking_client = client.NetworkingV1Api()
    logger.debug("NetworkingV1Api client initialized")
    return _networking_client


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


class NamespaceInput(BaseModel):
    """Input schema for namespace-scoped queries."""

    namespace: str = Field(
        default="",
        description="Kubernetes namespace. Leave empty for all namespaces."
    )


class GetNodeDetailsInput(BaseModel):
    """Input schema for getting node details."""

    node_name: str = Field(
        ...,  # Required
        description="Name of the node to get details for"
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


@tool(args_schema=NamespaceInput)
def list_deployments(namespace: str = "") -> str:
    """
    List deployments in the cluster.
    Use this to see deployment status, replica counts, and availability.
    """
    try:
        apps = get_apps_client()

        if namespace:
            deployments = apps.list_namespaced_deployment(namespace=namespace)
        else:
            deployments = apps.list_deployment_for_all_namespaces()

        if not deployments.items:
            return "No deployments found."

        lines = [f"Found {len(deployments.items)} deployments:\n"]

        for dep in deployments.items:
            ready = dep.status.ready_replicas or 0
            desired = dep.spec.replicas or 0
            available = dep.status.available_replicas or 0

            status = "✅" if ready == desired else "⚠️"
            lines.append(
                f"  {status} {dep.metadata.namespace}/{dep.metadata.name}: "
                f"{ready}/{desired} ready, {available} available"
            )

        return "\n".join(lines)

    except Exception as e:
        return f"Error listing deployments: {e}"


@tool(args_schema=NamespaceInput)
def list_services(namespace: str = "") -> str:
    """
    List services in the cluster.
    Use this to see service configuration, types, and cluster IPs.
    """
    try:
        v1 = get_k8s_client()

        if namespace:
            services = v1.list_namespaced_service(namespace=namespace)
        else:
            services = v1.list_service_for_all_namespaces()

        if not services.items:
            return "No services found."

        lines = [f"Found {len(services.items)} services:\n"]

        for svc in services.items:
            svc_type = svc.spec.type
            cluster_ip = svc.spec.cluster_ip or "None"
            ports = ", ".join(
                f"{p.port}/{p.protocol}" for p in (svc.spec.ports or [])
            )
            lines.append(
                f"  - {svc.metadata.namespace}/{svc.metadata.name}: "
                f"{svc_type}, IP: {cluster_ip}, Ports: [{ports}]"
            )

        return "\n".join(lines)

    except Exception as e:
        return f"Error listing services: {e}"


@tool(args_schema=NamespaceInput)
def list_ingresses(namespace: str = "") -> str:
    """
    List ingresses in the cluster.
    Use this to see HTTP/HTTPS routing rules, hosts, and backend services.
    """
    try:
        networking = get_networking_client()

        if namespace:
            ingresses = networking.list_namespaced_ingress(namespace=namespace)
        else:
            ingresses = networking.list_ingress_for_all_namespaces()

        if not ingresses.items:
            return "No ingresses found."

        lines = [f"Found {len(ingresses.items)} ingresses:\n"]

        for ing in ingresses.items:
            ing_class = ing.spec.ingress_class_name or "default"
            lines.append(
                f"  - {ing.metadata.namespace}/{ing.metadata.name} "
                f"(class: {ing_class})"
            )

            # Show rules
            for rule in (ing.spec.rules or []):
                host = rule.host or "*"
                if rule.http and rule.http.paths:
                    for path in rule.http.paths:
                        backend_svc = path.backend.service.name if path.backend.service else "N/A"
                        backend_port = ""
                        if path.backend.service and path.backend.service.port:
                            port = path.backend.service.port
                            backend_port = port.number or port.name or ""
                        path_value = path.path or "/"
                        path_type = path.path_type or "Prefix"
                        lines.append(
                            f"      {host}{path_value} ({path_type}) -> "
                            f"{backend_svc}:{backend_port}"
                        )

            # Show TLS hosts
            if ing.spec.tls:
                tls_hosts = []
                for tls in ing.spec.tls:
                    tls_hosts.extend(tls.hosts or [])
                if tls_hosts:
                    lines.append(f"      TLS: {', '.join(tls_hosts)}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error listing ingresses: {e}"


@tool
def list_nodes() -> str:
    """
    List all nodes in the cluster.
    Use this to see node status and check for node issues.
    """
    try:
        v1 = get_k8s_client()
        nodes = v1.list_node()

        if not nodes.items:
            return "No nodes found."

        lines = [f"Found {len(nodes.items)} nodes:\n"]

        for node in nodes.items:
            # Get Ready condition
            ready = "Unknown"
            for cond in node.status.conditions or []:
                if cond.type == "Ready":
                    ready = "Ready" if cond.status == "True" else "NotReady"
                    break

            status = "✅" if ready == "Ready" else "❌"
            roles = ",".join(
                k.replace("node-role.kubernetes.io/", "")
                for k in (node.metadata.labels or {}).keys()
                if k.startswith("node-role.kubernetes.io/")
            ) or "worker"

            lines.append(
                f"  {status} {node.metadata.name}: {ready}, roles: [{roles}]"
            )

        return "\n".join(lines)

    except Exception as e:
        return f"Error listing nodes: {e}"


@tool(args_schema=GetNodeDetailsInput)
def get_node_details(node_name: str) -> str:
    """
    Get detailed information about a specific node.
    Use this to investigate node conditions, capacity, and allocatable resources.
    """
    try:
        v1 = get_k8s_client()
        node = v1.read_node(name=node_name)

        lines = [f"Node: {node_name}"]

        # Conditions
        lines.append("\nConditions:")
        for cond in node.status.conditions or []:
            status = "✅" if cond.status == "True" else "❌"
            lines.append(f"  {status} {cond.type}: {cond.status}")
            if cond.message:
                lines.append(f"      Message: {cond.message}")

        # Capacity
        lines.append("\nCapacity:")
        for key, value in (node.status.capacity or {}).items():
            lines.append(f"  - {key}: {value}")

        # Allocatable
        lines.append("\nAllocatable:")
        for key, value in (node.status.allocatable or {}).items():
            lines.append(f"  - {key}: {value}")

        # Taints
        if node.spec.taints:
            lines.append("\nTaints:")
            for taint in node.spec.taints:
                lines.append(f"  - {taint.key}={taint.value}:{taint.effect}")

        return "\n".join(lines)

    except ApiException as e:
        if e.status == 404:
            return f"Node '{node_name}' not found"
        return f"Error getting node details: {e}"
    except Exception as e:
        return f"Error: {e}"


@tool(args_schema=NamespaceInput)
def list_configmaps(namespace: str = "") -> str:
    """
    List ConfigMaps in the cluster.
    Use this to see what configuration is available to pods.
    """
    try:
        v1 = get_k8s_client()

        if namespace:
            configmaps = v1.list_namespaced_config_map(namespace=namespace)
        else:
            configmaps = v1.list_config_map_for_all_namespaces()

        if not configmaps.items:
            return "No ConfigMaps found."

        lines = [f"Found {len(configmaps.items)} ConfigMaps:\n"]

        for cm in configmaps.items:
            keys = list((cm.data or {}).keys())
            key_count = len(keys)
            key_preview = ", ".join(keys[:3])
            if key_count > 3:
                key_preview += f", ... (+{key_count - 3} more)"

            lines.append(
                f"  - {cm.metadata.namespace}/{cm.metadata.name}: "
                f"{key_count} keys [{key_preview}]"
            )

        return "\n".join(lines)

    except Exception as e:
        return f"Error listing ConfigMaps: {e}"


@tool(args_schema=NamespaceInput)
def list_secrets(namespace: str = "") -> str:
    """
    List Secret names in the cluster (NOT the secret values).
    Use this to check if required secrets exist.
    """
    try:
        v1 = get_k8s_client()

        if namespace:
            secrets = v1.list_namespaced_secret(namespace=namespace)
        else:
            secrets = v1.list_secret_for_all_namespaces()

        if not secrets.items:
            return "No Secrets found."

        lines = [f"Found {len(secrets.items)} Secrets:\n"]

        for secret in secrets.items:
            secret_type = secret.type or "Opaque"
            key_count = len(secret.data or {})

            lines.append(
                f"  - {secret.metadata.namespace}/{secret.metadata.name}: "
                f"type={secret_type}, {key_count} keys"
            )

        return "\n".join(lines)

    except Exception as e:
        return f"Error listing Secrets: {e}"


# =============================================================================
# TOOL COLLECTION (for easy import)
# =============================================================================

kubernetes_tools = [
    get_events,
    get_node_details,
    get_pod_details,
    get_pod_logs,
    list_configmaps,
    list_deployments,
    list_ingresses,
    list_namespaces,
    list_nodes,
    list_pods,
    list_secrets,
    list_services,
]
