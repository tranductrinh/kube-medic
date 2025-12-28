"""
Helper functions for interacting with agents.
"""


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
                    return msg.content

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

    return final_response


def format_error(error: Exception) -> str:
    """Format an error message for display."""
    return f"❌ Error: {type(error).__name__}: {error}"


def truncate_text(text: str, max_length: int = 500) -> str:
    """Truncate text to a maximum length."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."