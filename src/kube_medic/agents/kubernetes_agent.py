"""
Kubernetes Agent: Handles pod, log, and event queries
This agent is "workers" that the supervisor delegates to.
"""

from langchain.agents import create_agent
from langchain_core.runnables import Runnable

from kube_medic.logging_config import get_logger
from kube_medic.tools.kubernetes import kubernetes_tools
from kube_medic.utils.helpers import get_llm

logger = get_logger(__name__)

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


# =============================================================================
# AGENT FACTORIES
# =============================================================================
# Using factory functions (not global variables) so agents are created on-demand.

def create_kubernetes_agent() -> Runnable:
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
    logger.info("Creating Kubernetes specialist agent...")
    llm = get_llm()

    agent = create_agent(
        model=llm,
        tools=kubernetes_tools,
        system_prompt=KUBERNETES_SYSTEM_PROMPT,
    )
    logger.info(f"Kubernetes agent created with {len(kubernetes_tools)} tools")
    return agent
