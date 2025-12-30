"""
Prometheus Agent: Handles PromQL queries for metrics and performance analysis.
This agent is a "worker" that the supervisor delegates to.
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

PROMETHEUS_SYSTEM_PROMPT = """You are a Prometheus metrics specialist.

Available tools:
- prometheus_query: Current values (instant)
- prometheus_query_range: Trends over time

Efficient rules:
- Query multiple metrics in ONE call using PromQL OR operator or multiple queries
- Limit to 2-3 queries max per request
- If query fails, try ONE alternative then move on

PROMQL syntax tips:
  WRONG: metric{label="x"} by (pod)
  RIGHT: sum(metric{label="x"}) by (pod)

Common queries:
  sum(rate(container_cpu_usage_seconds_total[5m])) by (pod)
  sum(container_memory_usage_bytes) by (pod)
  sum(kube_pod_container_status_restarts_total) by (pod)

Response format: Return ONE comprehensive summary with all metric findings."""


# =============================================================================
# AGENT FACTORIES
# =============================================================================
# Using factory functions (not global variables) so agents are created on-demand.

def create_prometheus_agent() -> Runnable:
    """
    Create the Prometheus specialist agent.

    This agent handles:
    - PromQL instant queries (current metrics)
    - PromQL range queries (trend analysis over time)

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
