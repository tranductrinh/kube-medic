"""
Email Agent: Handles sending email notifications with investigation results.
This agent is a "worker" that the supervisor delegates to.
"""

from langchain.agents import create_agent
from langchain_core.runnables import Runnable

from kube_medic.logging_config import get_logger
from kube_medic.tools.email import email_tools
from kube_medic.utils.helpers import get_llm

logger = get_logger(__name__)

# =============================================================================
# SYSTEM PROMPTS
# =============================================================================
# Keeping prompts as constants makes them easy to find and modify.

EMAIL_SYSTEM_PROMPT = """You are an email notification specialist. Send investigation reports.

Efficient rule: Call send_email exactly ONCE with all findings. Confirm success."""


# =============================================================================
# AGENT FACTORIES
# =============================================================================
# Using factory functions (not global variables) so agents are created on-demand.

def create_email_agent() -> Runnable:
    """
    Create the Email notification agent.

    This agent handles:
    - Composing and sending email notifications
    - Formatting investigation results for email delivery
    - Notifying stakeholders about alerts and findings

    Returns:
        A LangChain agent configured for email notifications
    """
    logger.info("Creating Email specialist agent...")
    llm = get_llm()

    agent = create_agent(
        model=llm,
        tools=email_tools,
        system_prompt=EMAIL_SYSTEM_PROMPT,
    )
    logger.info(f"Email agent created with {len(email_tools)} tools")
    return agent
