"""
Tools package for KubeMedic.

This package contains all tools that agents can use:
- kubernetes: K8s API tools (pods, logs, events)
- prometheus: Prometheus metrics tools
"""

from kube_medic.tools.kubernetes import (
    kubernetes_tools,
    list_namespaces,
    list_pods,
    get_pod_details,
    get_pod_logs,
    get_events,
)
from kube_medic.tools.prometheus import (
    prometheus_tools,
    prometheus_query,
    get_pod_cpu_memory,
    get_pod_restarts,
    get_cluster_health,
)

__all__ = [
    # Kubernetes
    "kubernetes_tools",
    "list_namespaces",
    "list_pods",
    "get_pod_details",
    "get_pod_logs",
    "get_events",
    # Prometheus
    "prometheus_tools",
    "prometheus_query",
    "get_pod_cpu_memory",
    "get_pod_restarts",
    "get_cluster_health",
]