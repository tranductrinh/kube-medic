"""
Kubernetes Agent: Handles K8s resource queries (pods, nodes, deployments, events, etc.)
This agent is a "worker" that the supervisor delegates to.
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

KUBERNETES_SYSTEM_PROMPT = """You are a Kubernetes expert. All tools are READ-ONLY.

Available tools:
- list_pods: Pod status and restarts
- get_pod_logs: Application logs
- get_pod_details: Deep pod info
- get_events: K8s events (crashes, scheduling)
- list_deployments, list_services, list_ingresses: Resource status
- list_nodes, get_node_details: Node info
- list_configmaps, list_secrets: Config resources (names only)

Efficient rules:
- Call MULTIPLE tools in parallel when possible
- For "check pods + logs + events": call list_pods, then get_pod_logs AND get_events together
- Focus on unhealthy/crashing pods
- Return ONE comprehensive response with all findings
- IMPORTANT: When namespace is NOT explicitly specified, ALWAYS search ALL namespaces first (leave namespace empty). Do NOT assume namespace from application name.

Response format:
- Resource status (what's healthy, what's not)
- Errors found in logs
- Relevant events
- Any anomalies discovered"""


# =============================================================================
# AGENT FACTORIES
# =============================================================================
# Using factory functions (not global variables) so agents are created on-demand.

def create_kubernetes_agent() -> Runnable:
    """
    Create the Kubernetes specialist agent.

    This agent handles:
    - Pod listing, details, and logs
    - Node status and details
    - Deployment status
    - Events (scheduling, crashes, etc.)
    - ConfigMaps and Secrets (names/keys only)
    - Services, ingresses, and namespaces

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
