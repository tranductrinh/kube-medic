"""
Helper functions for interacting with agents.
"""

import logging

from kube_medic.config import get_settings

logger = logging.getLogger(__name__)


def ask_agent(agent, query: str, thread_id: str = "default") -> str:
    """
    Send a query to an agent and get the response.

    Args:
        agent: The agent to query
        query: The user's question
        thread_id: Conversation thread identifier for memory

    Returns:
        The agent's final text response
    """
    logger.debug(f"Query thread {thread_id}: {query[:50]}...")
    config = {"configurable": {"thread_id": thread_id}}

    result = agent.invoke(
        {"messages": [{"role": "user", "content": query}]},
        config=config,
    )

    # Extract final response from messages
    for msg in reversed(result.get("messages", [])):
        if hasattr(msg, 'content') and msg.content:
            if hasattr(msg, 'type') and msg.type == 'ai':
                if not (hasattr(msg, 'tool_calls') and msg.tool_calls and not msg.content):
                    logger.debug(f"Response received from agent ({len(msg.content)} chars)")
                    return msg.content

    logger.warning(f"No response from agent for thread {thread_id}")
    return "No response from agent."


def stream_agent(
        agent,
        query: str,
        thread_id: str = "default",
        verbose: bool = True,
) -> str:
    """
    Stream agent responses with real-time output.
    """
    logger.debug(f"Streaming response for thread {thread_id}")
    config = {"configurable": {"thread_id": thread_id}}

    if verbose:
        print(f"\n{'='*60}")
        print(f"🧑 USER: {query}")
        print("=" * 60)

    final_response = ""

    for step in agent.stream(
            {"messages": [{"role": "user", "content": query}]},
            config=config,
    ):
        for update in step.values():
            for message in update.get("messages", []):
                if verbose:
                    message.pretty_print()

                if hasattr(message, 'content') and message.content:
                    if hasattr(message, 'type') and message.type == 'ai':
                        if not (hasattr(message, 'tool_calls') and message.tool_calls):
                            final_response = message.content

    logger.debug(f"Stream completed for thread {thread_id}")
    return final_response


def format_error(error: Exception) -> str:
    """Format an error message for display."""
    logger.debug(f"Formatting error: {type(error).__name__}")
    return f"❌ Error: {type(error).__name__}: {error}"


def truncate_text(text: str, max_length: int = None) -> str:
    """Truncate text to a maximum length."""
    if max_length is None:
        settings = get_settings()
        max_length = settings.text_truncate_max_length

    if len(text) <= max_length:
        return text

    logger.debug(f"Truncating text from {len(text)} to {max_length} chars")
    return text[:max_length] + "..."