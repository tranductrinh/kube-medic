"""
KubeMedic - Main Entry Point.

This module provides the CLI interface for the agent.

Usage:
    python -m kube_medic.main

    # Or after installation:
    kube-medic
"""

import sys
import time

from kube_medic.agents import create_supervisor_agent
from kube_medic.config import get_settings
from kube_medic.utils import stream_agent


def main() -> int:
    """
    Main entry point for Kube Medic.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # -------------------------------------------------------------------------
    # 1. Validate Configuration
    # -------------------------------------------------------------------------
    print("Starting KubeMedic...")

    try:
        settings = get_settings()
        print(f"   Prometheus: {settings.prometheus_url}")
    except Exception as e:
        print(f"\nConfiguration error: {e}")
        print("\nMake sure you have set these environment variables:")
        print("  - AZURE_OPENAI_ENDPOINT")
        print("  - AZURE_OPENAI_API_KEY")
        print("  - AZURE_OPENAI_DEPLOYMENT_NAME")
        print("  - PROMETHEUS_URL")
        return 1

    # -------------------------------------------------------------------------
    # 2. Create Agent
    # -------------------------------------------------------------------------
    try:
        print("   Creating agent...")
        agent = create_supervisor_agent(use_memory=True)
        print("   Agent ready!\n")
    except Exception as e:
        print(f"\nFailed to create agent: {e}")
        return 1

    # -------------------------------------------------------------------------
    # 3. Interactive Loop
    # -------------------------------------------------------------------------
    print("=" * 60)
    print("KUBE MEDIC - Kubernetes Troubleshooting Agent")
    print("=" * 60)
    print("Commands:")
    print("  - Type your question and press Enter")
    print("  - Type 'quit' or 'exit' to stop")
    print("  - Type 'new' to start a new conversation")
    print("=" * 60)

    # Create unique thread ID for this session
    thread_id = f"session-{int(time.time())}"

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
                print("\n  Goodbye!")
                break

            if user_input.lower() == "new":
                thread_id = f"session-{int(time.time())}"
                print(f"  Started new conversation")
                continue

            # Query the agent
            stream_agent(agent, user_input, thread_id=thread_id, verbose=True)

        except KeyboardInterrupt:
            print("\n\n  Goodbye!")
            break
        except Exception as e:
            print(f"\n  Error: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())