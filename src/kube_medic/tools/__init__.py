"""
Tools package for KubeMedic.

This package contains all tools that agents can use:
- kubernetes: K8s API tools (pods, nodes, deployments, services, ingresses, events, logs, configmaps, secrets)
- prometheus: PromQL tools (instant queries, range queries)
- network: HTTP connectivity tools (endpoint checks)
- email: Email notification tools (send_email)
"""

from kube_medic.tools.kubernetes import (
    kubernetes_tools,
    list_namespaces,
    list_pods,
    get_pod_details,
    get_pod_logs,
    get_events,
    list_deployments,
    list_services,
    list_ingresses,
    list_nodes,
    get_node_details,
    list_configmaps,
    list_secrets,
)
from kube_medic.tools.prometheus import (
    prometheus_tools,
    prometheus_query,
    prometheus_query_range,
)
from kube_medic.tools.network import (
    network_tools,
    http_check,
)
from kube_medic.tools.email import (
    email_tools,
    send_email,
)

__all__ = [
    # Kubernetes
    "kubernetes_tools",
    "list_namespaces",
    "list_pods",
    "get_pod_details",
    "get_pod_logs",
    "get_events",
    "list_deployments",
    "list_services",
    "list_ingresses",
    "list_nodes",
    "get_node_details",
    "list_configmaps",
    "list_secrets",
    # Prometheus
    "prometheus_tools",
    "prometheus_query",
    "prometheus_query_range",
    # Network
    "network_tools",
    "http_check",
    # Email
    "email_tools",
    "send_email",
]
