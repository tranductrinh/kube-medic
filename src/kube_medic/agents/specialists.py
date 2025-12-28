"""
Specialist Agents.

This module defines the specialist agents:
- Kubernetes Agent: Handles pod, log, and event queries
- Prometheus Agent: Handles metrics and health queries

These agents are "workers" that the supervisor delegates to.
"""

from langchain.agents import create_agent
from langchain_openai import AzureChatOpenAI

from kube_medic.config import get_settings
from kube_medic.tools.kubernetes import kubernetes_tools
from kube_medic.tools.prometheus import prometheus_tools


# =============================================================================
# LLM FACTORY (Singleton Pattern)
# =============================================================================

_llm_instance: AzureChatOpenAI | None = None


def get_llm() -> AzureChatOpenAI:
    """
    Get or create the LLM instance.

    Uses singleton pattern - only creates LLM once.
    All agents share the same LLM instance.
    """
    global _llm_instance

    if _llm_instance is not None:
        return _llm_instance

    settings = get_settings()

    _llm_instance = AzureChatOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        azure_deployment=settings.azure_openai_deployment_name,
        api_version="2024-08-01-preview",
        temperature=0,
        max_tokens=2048,
    )

    return _llm_instance


# =============================================================================
# SYSTEM PROMPTS
# =============================================================================
# Keeping prompts as constants makes them easy to find and modify.

KUBERNETES_SYSTEM_PROMPT = """You are a Kubernetes expert. You help investigate Kubernetes 
resources, pod states, logs, and events.

Your tools:
- list_namespaces: See cluster namespaces
- list_pods: Check pod status and restarts
- get_pod_details: Deep dive into specific pods
- get_pod_logs: Read application logs
- get_events: Find K8s events (scheduling, crashes, etc.)

IMPORTANT: Always include ALL relevant findings in your response. 
The supervisor depends on your complete answer."""


PROMETHEUS_SYSTEM_PROMPT = """You are a Prometheus metrics expert. You help analyze 
cluster performance, resource usage, and stability metrics.

Your tools:
- get_cluster_health: Quick health overview
- get_pod_cpu_memory: Find resource-hungry pods
- get_pod_restarts: Find unstable/crashing pods
- prometheus_query: Run custom PromQL queries

IMPORTANT: Always include ALL relevant findings in your response.
The supervisor depends on your complete answer."""


# =============================================================================
# AGENT FACTORIES
# =============================================================================
# Using factory functions (not global variables) so agents are created on-demand.

def create_kubernetes_agent():
    """
    Create the Kubernetes specialist agent.

    This agent handles:
    - Pod listing and details
    - Log retrieval
    - Event queries
    - Namespace exploration

    Returns:
        A LangChain agent configured for K8s troubleshooting
    """
    llm = get_llm()

    return create_agent(
        model=llm,
        tools=kubernetes_tools,
        system_prompt=KUBERNETES_SYSTEM_PROMPT,
    )


def create_prometheus_agent():
    """
    Create the Prometheus specialist agent.

    This agent handles:
    - Cluster health checks
    - CPU/memory metrics
    - Restart counts
    - Custom PromQL queries

    Returns:
        A LangChain agent configured for metrics analysis
    """
    llm = get_llm()

    return create_agent(
        model=llm,
        tools=prometheus_tools,
        system_prompt=PROMETHEUS_SYSTEM_PROMPT,
    )