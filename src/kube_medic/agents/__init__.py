"""
Agents package for KubeMedic.

This package contains:
- specialists: Kubernetes and Prometheus specialist agents
- supervisor: The main supervisor agent that coordinates specialists

Usage:
    from kube_medic.agents import create_supervisor_agent

    agent = create_supervisor_agent()
"""
from kube_medic.agents.kubernetes_agent import create_kubernetes_agent
from kube_medic.agents.prometheus_agent import create_prometheus_agent
from kube_medic.agents.supervisor import create_supervisor_agent

__all__ = [
    "create_kubernetes_agent",
    "create_prometheus_agent",
    "create_supervisor_agent",
]
