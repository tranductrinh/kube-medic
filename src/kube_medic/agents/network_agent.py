"""
Network Agent: Handles HTTP connectivity checks and network diagnostics.
This agent is a "worker" that the supervisor delegates to.
"""

from langchain.agents import create_agent
from langchain_core.runnables import Runnable

from kube_medic.logging_config import get_logger
from kube_medic.tools.network import network_tools
from kube_medic.utils.helpers import get_llm

logger = get_logger(__name__)

# =============================================================================
# SYSTEM PROMPTS
# =============================================================================
# Keeping prompts as constants makes them easy to find and modify.

NETWORK_SYSTEM_PROMPT = """You are a network connectivity expert. You help verify that
HTTP/HTTPS endpoints are accessible and diagnose connectivity issues.

Your tools:
- http_check: Check if an HTTP/HTTPS endpoint is accessible (status code, response time)

Use cases:
- Verify ingress endpoints are reachable
- Check health endpoints
- Test API availability
- Diagnose SSL/TLS issues
- Measure response times

IMPORTANT: Always include ALL relevant findings in your response.
The supervisor depends on your complete answer."""


# =============================================================================
# AGENT FACTORIES
# =============================================================================
# Using factory functions (not global variables) so agents are created on-demand.

def create_network_agent() -> Runnable:
    """
    Create the Network specialist agent.

    This agent handles:
    - HTTP/HTTPS endpoint connectivity checks
    - Response time measurements
    - SSL certificate verification
    - Redirect following

    Returns:
        A LangChain agent configured for network diagnostics
    """
    logger.info("Creating Network specialist agent...")
    llm = get_llm()

    agent = create_agent(
        model=llm,
        tools=network_tools,
        system_prompt=NETWORK_SYSTEM_PROMPT,
    )
    logger.info(f"Network agent created with {len(network_tools)} tools")
    return agent
