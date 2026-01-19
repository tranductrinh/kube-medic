"""
Supervisor Agent.

This module defines the supervisor agent that coordinates specialist agents
and maintains conversation memory.
"""

from threading import Lock
from typing import Any

from cachetools import TTLCache
from langchain.agents import create_agent
from langchain_core.runnables import Runnable
from langchain_core.tools import tool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field

from kube_medic.agents.email_agent import create_email_agent
from kube_medic.agents.kubernetes_agent import create_kubernetes_agent
from kube_medic.agents.network_agent import create_network_agent
from kube_medic.agents.prometheus_agent import create_prometheus_agent
from kube_medic.config import get_settings
from kube_medic.logging_config import get_logger
from kube_medic.utils.helpers import get_llm

logger = get_logger(__name__)


# =============================================================================
# BOUNDED MEMORY SAVER (TTL + Max Size)
# =============================================================================

class BoundedMemorySaver(BaseCheckpointSaver):
    """
    Memory saver with TTL and max size limits to prevent unbounded growth.

    This implementation wraps conversation checkpoints in a TTLCache that
    automatically evicts old entries based on time and size limits.
    """

    def __init__(self, maxsize: int = 1000, ttl: int = 3600):
        """
        Initialize bounded memory saver.

        Args:
            maxsize: Maximum number of conversation threads to keep
            ttl: Time-to-live in seconds for each thread
        """
        super().__init__()
        self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)
        self._lock = Lock()
        self._maxsize = maxsize
        self._ttl = ttl
        logger.info(f"BoundedMemorySaver initialized (maxsize={maxsize}, ttl={ttl}s)")

    def _get_key(self, config: dict[str, Any]) -> str:
        """Extract thread ID from config."""
        return config.get("configurable", {}).get("thread_id", "default")

    def get_tuple(self, config: dict[str, Any]):
        """Get checkpoint tuple for a thread."""
        with self._lock:
            key = self._get_key(config)
            result = self._cache.get(key)
            if result:
                logger.debug(f"Memory cache hit for thread: {key}")
            return result

    def put(self, config: dict[str, Any], checkpoint: dict[str, Any], metadata: dict[str, Any], new_versions: dict[str, Any]) -> dict[str, Any]:
        """Store checkpoint for a thread."""
        with self._lock:
            key = self._get_key(config)
            checkpoint_tuple = (checkpoint, metadata, new_versions)
            self._cache[key] = checkpoint_tuple
            logger.debug(f"Memory cache stored for thread: {key} (cache size: {len(self._cache)})")
            return config

    def list(self, config: dict[str, Any] | None = None, *, filter: dict[str, Any] | None = None, before: dict[str, Any] | None = None, limit: int | None = None):
        """List checkpoints (yields stored checkpoints)."""
        with self._lock:
            for key, value in self._cache.items():
                yield {"configurable": {"thread_id": key}}, value

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics for monitoring."""
        with self._lock:
            return {
                "current_size": len(self._cache),
                "max_size": self._maxsize,
                "ttl_seconds": self._ttl,
                "threads": list(self._cache.keys())[:20],  # First 20 thread IDs
            }


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

SUPERVISOR_SYSTEM_PROMPT = """You are a Kubernetes troubleshooting supervisor. Find the ROOT CAUSE efficiently.

Available tools:
- ask_kubernetes_expert: pods, logs, events, services, deployments, ingresses
- ask_prometheus_expert: CPU/memory metrics, error rates, resource trends
- ask_network_expert: HTTP endpoint connectivity checks
- ask_email_expert: send investigation report (ALWAYS call after investigation)

Efficient rules:
- Make ONE comprehensive request per expert - ask for everything you need at once
- BAD: "list pods" then "get logs for pod X" then "get events" (3 calls)
- GOOD: "List all pods, get logs and events for any unhealthy ones" (1 call)
- Limit to 2-3 expert calls total before concluding
- "Running" status does NOT mean healthy - always request logs

Investigation steps:
1. Ask kubernetes_expert for: pod status + logs + events (one comprehensive request)
2. If metrics needed, ask prometheus_expert once for all relevant metrics
3. Conclude with root cause and fix
4. Send the report by email

Response format:
- Summary: concise overview of issue
- Root cause: concise explanation
- Evidence: what was checked and found
- Fix: specific kubectl commands (never auto-execute) or other steps"""


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
    - Sends email notifications after investigations

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
    email_agent = create_email_agent()

    # -------------------------------------------------------------------------
    # Wrap specialists as tools
    # -------------------------------------------------------------------------
    # This is the key pattern: agents become tools that supervisor can call

    @tool(args_schema=AgentQueryInput)
    def ask_kubernetes_expert(request: str) -> str:
        """Query Kubernetes resources: pods, logs, events, deployments, services, ingresses."""
        logger.debug("Delegating to Kubernetes expert")
        return run_agent(kubernetes_agent, request)

    @tool(args_schema=AgentQueryInput)
    def ask_prometheus_expert(request: str) -> str:
        """Query Prometheus metrics: CPU, memory, error rates, resource trends."""
        logger.debug("Delegating to Prometheus expert")
        return run_agent(prometheus_agent, request)

    @tool(args_schema=AgentQueryInput)
    def ask_network_expert(request: str) -> str:
        """Check HTTP/HTTPS endpoint connectivity and response times."""
        logger.debug("Delegating to Network expert")
        return run_agent(network_agent, request)

    @tool(args_schema=AgentQueryInput)
    def ask_email_expert(request: str) -> str:
        """Send investigation report via email. Recipient is pre-configured."""
        logger.debug("Delegating to Email expert")
        return run_agent(email_agent, request)

    # Agent tools for supervisor
    agent_tools = [ask_kubernetes_expert, ask_prometheus_expert, ask_network_expert, ask_email_expert]

    # Create checkpointer for memory (if enabled)
    # Uses BoundedMemorySaver to prevent unbounded memory growth
    checkpointer = None
    if use_memory:
        settings = get_settings()
        checkpointer = BoundedMemorySaver(
            maxsize=settings.memory_max_threads,
            ttl=settings.memory_ttl_seconds,
        )
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
