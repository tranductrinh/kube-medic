"""
Supervisor Agent.

This module defines the supervisor agent that coordinates specialist agents
and maintains conversation memory.
"""

from langchain.agents import create_agent
from langchain_core.runnables import Runnable
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel, Field

from kube_medic.agents.kubernetes_agent import create_kubernetes_agent
from kube_medic.agents.prometheus_agent import create_prometheus_agent
from kube_medic.agents.network_agent import create_network_agent
from kube_medic.logging_config import get_logger
from kube_medic.utils.helpers import get_llm

logger = get_logger(__name__)


# =============================================================================
# AGENT QUERY SCHEMA
# =============================================================================

class AgentQueryInput(BaseModel):
    """Input schema for delegating to specialist agents."""

    request: str = Field(
        ...,
        description="The question or task to delegate to this agent"
    )


# =============================================================================
# AGENT RUNNER HELPER
# =============================================================================

def run_agent(agent, request: str) -> str:
    """
    Run an agent and extract its final response.

    Args:
        agent: The agent to run
        request: The query to send to the agent

    Returns:
        The agent's final text response
    """
    logger.debug(f"Running agent with request: {request[:50]}...")
    result = agent.invoke({"messages": [{"role": "user", "content": request}]})

    # Get the last AI message with content
    for msg in reversed(result.get("messages", [])):
        if hasattr(msg, 'content') and msg.content:
            if hasattr(msg, 'type') and msg.type == 'ai':
                if not (hasattr(msg, 'tool_calls') and msg.tool_calls and not msg.content):
                    logger.debug(f"Agent response obtained ({len(msg.content)} chars)")
                    return msg.content

    logger.warning("No response from agent")
    return "No response from agent."


# =============================================================================
# SUPERVISOR SYSTEM PROMPT
# =============================================================================

SUPERVISOR_SYSTEM_PROMPT = """You are a Kubernetes troubleshooting supervisor. Your goal is to find the ROOT CAUSE, not just symptoms.

INVESTIGATION RULES:
- "Running" status does NOT mean healthy - always check logs
- When you find an error, investigate its source (e.g., DB error → check DB pod)
- Keep investigating until you identify the root cause
- Do NOT stop to ask the user if they want to continue - just investigate

YOUR EXPERTS:
- ask_kubernetes_expert: pods, logs, events, services, endpoints, ingresses, deployments
- ask_prometheus_expert: CPU/memory, error rates, restarts, metrics
- ask_network_expert: HTTP connectivity (use ingress hostname, never internal IPs)

HOW TO INVESTIGATE:
1. Start with the reported problem (check status, logs, connectivity)
2. Follow the error trail - each error points to the next thing to check
3. Check dependencies (app error → database? external service? config?)
4. Stop only when you find the root cause or exhaust all leads

RESPONSE FORMAT (only after finding root cause):
- ❌ Root Cause and ⚠️ Contributing Factors
- Evidence Trail: what you checked and found
- Actionable Fix: provide specific kubectl commands or scripts to fix the issue (never auto-execute)"""


# =============================================================================
# SUPERVISOR FACTORY
# =============================================================================

def create_supervisor_agent(use_memory: bool = True) -> Runnable:
    """
    Create the supervisor agent with optional memory.

    The supervisor:
    - Routes questions to specialist agents
    - Synthesizes responses
    - Maintains conversation context (if memory enabled)

    Args:
        use_memory: Whether to enable conversation memory (default: True)

    Returns:
        The configured supervisor agent
    """
    logger.info("Creating supervisor agent...")
    llm = get_llm()

    # Create specialist agents
    logger.debug("Initializing specialist agents...")
    kubernetes_agent = create_kubernetes_agent()
    prometheus_agent = create_prometheus_agent()
    network_agent = create_network_agent()

    # -------------------------------------------------------------------------
    # Wrap specialists as tools
    # -------------------------------------------------------------------------
    # This is the key pattern: agents become tools that supervisor can call

    @tool(args_schema=AgentQueryInput)
    def ask_kubernetes_expert(request: str) -> str:
        """
        Delegate a question to the Kubernetes Specialist Agent.

        Use this for questions about:
        - Pod status, health, and restarts
        - Container logs and errors
        - Kubernetes events and warnings
        - Namespace and resource structure
        - Deployment and ingress configuration

        Example: "Check if any pods are crashing in the monitoring-system namespace"
        """
        logger.debug("Delegating to Kubernetes expert")
        return run_agent(kubernetes_agent, request)

    @tool(args_schema=AgentQueryInput)
    def ask_prometheus_expert(request: str) -> str:
        """
        Delegate a question to the Prometheus Specialist Agent.

        Use this for questions about:
        - CPU and memory usage
        - Resource consumption trends
        - Pod restart counts and stability
        - Cluster health overview
        - Performance metrics

        Example: "Which pods are using the most CPU right now?"
        """
        logger.debug("Delegating to Prometheus expert")
        return run_agent(prometheus_agent, request)

    @tool(args_schema=AgentQueryInput)
    def ask_network_expert(request: str) -> str:
        """
        Delegate a question to the Network Specialist Agent.

        Use this for questions about:
        - HTTP/HTTPS endpoint accessibility
        - Ingress connectivity verification
        - Response time measurements
        - SSL certificate issues
        - API endpoint health checks

        Example: "Check if https://api.example.com/health is accessible"
        """
        logger.debug("Delegating to Network expert")
        return run_agent(network_agent, request)

    # Agent tools for supervisor
    agent_tools = [ask_kubernetes_expert, ask_prometheus_expert, ask_network_expert]

    # Create checkpointer for memory (if enabled)
    checkpointer = InMemorySaver() if use_memory else None
    logger.info(f"Memory enabled: {use_memory}")

    # Create supervisor agent
    supervisor = create_agent(
        model=llm,
        tools=agent_tools,
        system_prompt=SUPERVISOR_SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
    logger.info("Supervisor agent created successfully")
    return supervisor
