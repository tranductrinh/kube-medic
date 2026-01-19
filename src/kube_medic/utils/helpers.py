"""
Helper functions for KubeMedic.

This module provides:
- get_llm: LLM singleton factory (OpenAI-compatible endpoint)
- ask_agent: Ask agent with detailed DEBUG logging and recursion monitoring
- format_error: Format exceptions for display
- truncate_text: Truncate text to max length
- parse_relative_time: Parse time strings like '1h', '30m', 'now'
- get_recursion_stats: Get recursion limit hit statistics
"""

import re
from collections import Counter
from datetime import datetime, timedelta
from threading import Lock
from typing import Any

from langchain_openai import ChatOpenAI

from kube_medic.config import get_settings
from kube_medic.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# RECURSION MONITORING
# =============================================================================

_recursion_limit_hits: Counter = Counter()
_recursion_lock = Lock()
_total_agent_invocations = 0
_invocations_lock = Lock()


def get_recursion_stats() -> dict[str, Any]:
    """
    Get recursion limit hit statistics for monitoring.

    Returns:
        Dict with recursion limit statistics including:
        - total_hits: Total number of recursion limit hits
        - total_invocations: Total agent invocations
        - hit_rate: Percentage of invocations that hit the limit
        - by_thread: Hits per thread (top 20)
    """
    with _recursion_lock:
        total_hits = sum(_recursion_limit_hits.values())
        by_thread = dict(_recursion_limit_hits.most_common(20))

    with _invocations_lock:
        total_invocations = _total_agent_invocations

    hit_rate = (total_hits / total_invocations * 100) if total_invocations > 0 else 0

    return {
        "total_hits": total_hits,
        "total_invocations": total_invocations,
        "hit_rate_percent": round(hit_rate, 2),
        "by_thread": by_thread,
    }


def _record_recursion_limit_hit(thread_id: str) -> None:
    """Record a recursion limit hit for monitoring and alerting."""
    with _recursion_lock:
        _recursion_limit_hits[thread_id] += 1
        total_hits = sum(_recursion_limit_hits.values())

    # Log warning for every hit
    logger.warning(
        f"[{thread_id}] Agent hit recursion limit! "
        f"Thread hits: {_recursion_limit_hits[thread_id]}, Total: {total_hits}"
    )

    # Log critical alert periodically (every 10 hits)
    if total_hits % 10 == 0:
        logger.critical(
            f"ALERT: Recursion limit hit {total_hits} times total! "
            f"Consider increasing agent_recursion_limit or investigating agent behavior."
        )


def _record_invocation() -> None:
    """Record an agent invocation for statistics."""
    global _total_agent_invocations
    with _invocations_lock:
        _total_agent_invocations += 1

# =============================================================================
# LLM FACTORY (Singleton Pattern)
# =============================================================================

_llm_instance: ChatOpenAI | None = None


def get_llm() -> ChatOpenAI:
    """
    Get or create the LLM instance.

    Uses singleton pattern - only creates LLM once.
    All agents share the same LLM instance.
    Supports OpenAI-compatible endpoints (Azure OpenAI with /openai/v1/ format).
    """
    global _llm_instance

    if _llm_instance is not None:
        logger.debug("Reusing existing LLM instance")
        return _llm_instance

    logger.info("Initializing LLM instance...")
    settings = get_settings()

    _llm_instance = ChatOpenAI(
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )

    logger.info(f"LLM initialized (model={settings.openai_model}, temp={settings.llm_temperature}, max_tokens={settings.llm_max_tokens})")
    return _llm_instance


def ask_agent(
        agent,
        query: str,
        thread_id: str = "default",
) -> str:
    """
    Ask the agent a question with detailed logging of tool calls and responses.

    This function streams the agent execution and logs each step at DEBUG level,
    making it ideal for API/server usage where you want visibility into the
    agent's reasoning without printing to stdout.

    Features:
    - Recursion limit monitoring with alerting
    - Detailed tool call logging
    - Invocation statistics tracking

    Args:
        agent: The agent to query
        query: The user's question
        thread_id: Conversation thread identifier for memory

    Returns:
        The agent's final text response

    Logs (at DEBUG level):
        - Each tool call with arguments
        - Tool results (truncated)
        - AI intermediate thoughts
        - Final response
    """
    logger.debug(f"[{thread_id}] Starting agent invocation")

    # Track invocation for statistics
    _record_invocation()

    settings = get_settings()
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": settings.agent_recursion_limit,
    }

    final_response = ""
    tool_call_count = 0
    hit_recursion_limit = False

    try:
        for step in agent.stream(
                {"messages": [{"role": "user", "content": query}]},
                config=config,
        ):
            for node_name, update in step.items():
                for message in update.get("messages", []):
                    msg_type = getattr(message, 'type', 'unknown')

                    # Log tool calls from AI
                    if hasattr(message, 'tool_calls') and message.tool_calls:
                        for tool_call in message.tool_calls:
                            tool_call_count += 1
                            tool_name = tool_call.get('name', 'unknown')
                            tool_args = tool_call.get('args', {})
                            # Truncate long arguments for readability
                            args_str = str(tool_args)
                            if len(args_str) > 200:
                                args_str = args_str[:200] + "..."
                            logger.debug(
                                f"[{thread_id}] Tool call #{tool_call_count}: "
                                f"{tool_name}({args_str})"
                            )

                    # Log tool results
                    if msg_type == 'tool':
                        tool_name = getattr(message, 'name', 'unknown')
                        content = getattr(message, 'content', '')
                        # Truncate long tool results
                        content_preview = content[:500] + "..." if len(content) > 500 else content
                        logger.debug(
                            f"[{thread_id}] Tool result from {tool_name}: "
                            f"{content_preview}"
                        )

                    # Log AI messages (thoughts and final response)
                    if msg_type == 'ai' and hasattr(message, 'content') and message.content:
                        content = message.content
                        has_tool_calls = hasattr(message, 'tool_calls') and message.tool_calls

                        if has_tool_calls:
                            # AI is thinking and will call tools
                            if content:
                                thought_preview = content[:300] + "..." if len(content) > 300 else content
                                logger.debug(f"[{thread_id}] AI thinking: {thought_preview}")
                        else:
                            # Final response (no more tool calls)
                            final_response = content
                            logger.debug(
                                f"[{thread_id}] AI final response: "
                                f"{content[:300]}{'...' if len(content) > 300 else ''}"
                            )

    except RecursionError as e:
        # Agent hit recursion limit - record for monitoring
        hit_recursion_limit = True
        _record_recursion_limit_hit(thread_id)
        final_response = (
            f"Investigation incomplete: Agent reached maximum iterations "
            f"({settings.agent_recursion_limit}). The investigation was cut short. "
            f"Consider breaking down the query into smaller parts."
        )
        logger.error(f"[{thread_id}] RecursionError: {e}")

    except Exception as e:
        # Check if this is a recursion-related error from LangGraph
        error_str = str(e).lower()
        if "recursion" in error_str or "maximum" in error_str:
            hit_recursion_limit = True
            _record_recursion_limit_hit(thread_id)
            final_response = (
                f"Investigation incomplete: Agent reached maximum iterations "
                f"({settings.agent_recursion_limit}). Error: {e}"
            )
        else:
            # Re-raise non-recursion errors
            raise

    logger.debug(
        f"[{thread_id}] Agent invocation complete, {tool_call_count} tool calls made"
        + (", HIT RECURSION LIMIT" if hit_recursion_limit else "")
    )
    return final_response if final_response else "No response from agent."


def format_error(error: Exception) -> str:
    """Format an error message for display."""
    logger.debug(f"Formatting error: {type(error).__name__}")
    return f"Error: {type(error).__name__}: {error}"


def truncate_text(text: str, max_length: int = None) -> str:
    """Truncate text to a maximum length."""
    if max_length is None:
        settings = get_settings()
        max_length = settings.text_truncate_max_length

    if len(text) <= max_length:
        return text

    logger.debug(f"Truncating text from {len(text)} to {max_length} chars")
    return text[:max_length] + "..."


def parse_relative_time(time_str: str) -> datetime:
    """
    Parse relative time string to datetime.

    Args:
        time_str: Time string like '1h', '30m', '2d', 'now', or ISO timestamp

    Returns:
        datetime object
    """
    if time_str == "now":
        return datetime.now()

    # Try relative time (e.g., "1h", "30m", "2d")
    match = re.match(r'^(\d+)([smhdw])$', time_str)
    if match:
        value = int(match.group(1))
        unit = match.group(2)

        unit_map = {
            's': timedelta(seconds=value),
            'm': timedelta(minutes=value),
            'h': timedelta(hours=value),
            'd': timedelta(days=value),
            'w': timedelta(weeks=value),
        }

        return datetime.now() - unit_map[unit]

    # Try ISO timestamp
    try:
        return datetime.fromisoformat(time_str)
    except ValueError:
        raise ValueError(f"Invalid time format: {time_str}. Use '1h', '30m', 'now', or ISO timestamp.")
