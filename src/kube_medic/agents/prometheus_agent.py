"""
Prometheus Agent: Handles metrics and health queries
This agent is "workers" that the supervisor delegates to.
"""

from langchain.agents import create_agent
from langchain_core.runnables import Runnable

from kube_medic.logging_config import get_logger
from kube_medic.tools.prometheus import prometheus_tools
from kube_medic.utils.helpers import get_llm

logger = get_logger(__name__)

# =============================================================================
# SYSTEM PROMPTS
# =============================================================================
# Keeping prompts as constants makes them easy to find and modify.

PROMETHEUS_SYSTEM_PROMPT = """You are a Prometheus metrics expert. You help analyze 
cluster performance, resource usage, and stability metrics by using PromQL.

Your tools:
- prometheus_query: Run PromQL instant queries
- prometheus_query_range: Run PromQL range queries for trend analysis

IMPORTANT: Always include ALL relevant findings in your response.
The supervisor depends on your complete answer."""


# =============================================================================
# AGENT FACTORIES
# =============================================================================
# Using factory functions (not global variables) so agents are created on-demand.

def create_prometheus_agent() -> Runnable:
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
    logger.info("Creating Prometheus specialist agent...")
    llm = get_llm()

    agent = create_agent(
        model=llm,
        tools=prometheus_tools,
        system_prompt=PROMETHEUS_SYSTEM_PROMPT,
    )
    logger.info(f"Prometheus agent created with {len(prometheus_tools)} tools")
    return agent
