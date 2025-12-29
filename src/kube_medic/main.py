"""
KubeMedic - Main Entry Point.

This module provides the CLI interface for the agent.

Usage:
    python -m kube_medic.main

    # Or after installation:
    kube-medic
"""

import logging
import sys
import time

from kube_medic.agents import create_supervisor_agent
from kube_medic.config import get_settings
from kube_medic.logging_config import setup_logging, get_logger
from kube_medic.utils import stream_agent

logger = get_logger(__name__)


def main() -> int:
    """
    Main entry point for KubeMedic.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    setup_logging()

    # -------------------------------------------------------------------------
    # Validate Configuration
    # -------------------------------------------------------------------------
    logger.info("Starting KubeMedic...")

    try:
        settings = get_settings()
        logger.info(f"Prometheus URL: {settings.prometheus_url}")
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Make sure you have set these environment variables:")
        logger.error("  - AZURE_OPENAI_ENDPOINT")
        logger.error("  - AZURE_OPENAI_API_KEY")
        logger.error("  - AZURE_OPENAI_DEPLOYMENT_NAME")
        logger.error("  - PROMETHEUS_URL")
        return 1

    # -------------------------------------------------------------------------
    # Create Agent
    # -------------------------------------------------------------------------
    try:
        logger.info("Creating supervisor agent...")
        agent = create_supervisor_agent(use_memory=True)
        logger.info("Agent ready!")
    except Exception as e:
        logger.error(f"Failed to create agent: {e}", exc_info=True)
        return 1

    # -------------------------------------------------------------------------
    # Interactive Loop
    # -------------------------------------------------------------------------
    print("=" * 60)
    print("KUBE MEDIC - AI-powered Kubernetes troubleshooting assistant")
    print("=" * 60)
    print("Commands:")
    print("  - Type your question and press Enter")
    print("  - Type 'quit' or 'exit' to stop")
    print("  - Type 'new' to start a new conversation")
    print("=" * 60)

    logger.info("Interactive mode started")

    # Create unique thread ID for this session
    thread_id = f"session-{int(time.time())}"
    logger.debug(f"Session thread ID: {thread_id}")

    while True:
        try:
            # Get user input
            print()
            user_input = input("  You: ").strip()

            # Skip empty input
            if not user_input:
                continue

            # Handle commands
            if user_input.lower() in ("quit", "exit", "q"):
                logger.info("User requested exit")
                print("\n  Goodbye!")
                break

            if user_input.lower() == "new":
                thread_id = f"session-{int(time.time())}"
                logger.info(f"Started new conversation with thread ID: {thread_id}")
                print(f"  Started new conversation")
                continue

            logger.debug(f"Processing user query: {user_input[:50]}...")

            # Query the agent
            stream_agent(agent, user_input, thread_id=thread_id, verbose=True)

        except KeyboardInterrupt:
            logger.info("Interrupted by user (Ctrl+C)")
            print("\n\n  Goodbye!")
            break
        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            print(f"\n  Error: {e}")

    logger.info("KubeMedic session ended")
    return 0


if __name__ == "__main__":
    sys.exit(main())