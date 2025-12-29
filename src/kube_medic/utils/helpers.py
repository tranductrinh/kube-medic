"""
Helper functions.
"""

from langchain_openai import AzureChatOpenAI

from kube_medic.config import get_settings
from kube_medic.logging_config import get_logger

logger = get_logger(__name__)

# =============================================================================
# LLM FACTORY (Singleton Pattern)
# =============================================================================

_llm_instance: AzureChatOpenAI | None = None


def get_llm() -> AzureChatOpenAI:
    """
    Get or create the LLM instance.

    Uses singleton pattern - only creates LLM once.
    All agents share the same LLM instance.
    """
    global _llm_instance

    if _llm_instance is not None:
        logger.debug("Reusing existing LLM instance")
        return _llm_instance

    logger.info("Initializing LLM instance...")
    settings = get_settings()

    _llm_instance = AzureChatOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        azure_deployment=settings.azure_openai_deployment_name,
        api_version=settings.azure_openai_api_version,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )

    logger.info(f"LLM initialized (temp={settings.llm_temperature}, max_tokens={settings.llm_max_tokens})")
    return _llm_instance


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
        print(f"\n{'=' * 60}")
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
