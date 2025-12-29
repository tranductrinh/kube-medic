"""
Supervisor Agent.

This module defines the supervisor agent that coordinates specialist agents
and maintains conversation memory.
"""

import logging

from kube_medic.agents.specialists import (
    create_kubernetes_agent,
    create_prometheus_agent,
    get_llm,
)
from langchain.agents import create_agent
from langchain_core.runnables import Runnable
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


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

SUPERVISOR_SYSTEM_PROMPT = """You are a Kubernetes troubleshooting supervisor. You coordinate 
specialist agents to diagnose cluster issues.

YOUR TEAM:
1. ask_kubernetes_expert - For pod status, logs, events, and K8s resources
2. ask_metrics_expert - For CPU/memory usage, restarts, and performance metrics

WORKFLOW:
1. Understand what the user is asking
2. Decide which expert(s) to consult
3. Delegate specific questions to the right expert
4. Synthesize their findings into a clear answer

GUIDELINES:
- For general health checks: Start with metrics expert for overview
- For specific pod issues: Use K8s expert for logs/events, metrics expert for resources
- For performance issues: Use metrics expert first, then K8s for details
- You can consult BOTH experts if needed for a complete picture

RESPONSE FORMAT:
- Summarize findings clearly
- Highlight any issues found (⚠️ warnings, ❌ errors)
- Provide actionable recommendations
- NEVER try to fix things automatically

Be concise but thorough.

IMPORTANT: Remember our conversation context!
When delegating to specialists, include relevant context from our discussion."""


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
        - Deployment issues

        Example: "Check if any pods are crashing in the monitoring-system namespace"
        """
        logger.debug("Delegating to Kubernetes expert")
        return run_agent(kubernetes_agent, request)

    @tool(args_schema=AgentQueryInput)
    def ask_metrics_expert(request: str) -> str:
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

    # Agent tools for supervisor
    agent_tools = [ask_kubernetes_expert, ask_metrics_expert]

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
