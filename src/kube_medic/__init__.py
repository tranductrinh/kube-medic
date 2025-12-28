"""
KubeMedic - AI-powered Kubernetes Troubleshooting Agent.

A multi-agent system using LangChain to diagnose Kubernetes cluster issues.

Quick Start:
    from kube_medic import create_supervisor_agent, ask_agent

    # Create the agent
    agent = create_supervisor_agent()
    
    # Ask questions (same thread_id = same conversation)
    response = ask_agent(agent, "Check cluster health", thread_id="user-123")
    print(response)
    
    # Follow-up question (remembers context)
    response = ask_agent(agent, "Which pod has the most restarts?", thread_id="user-123")
    print(response)

Streaming:
    from kube_medic import create_supervisor_agent, stream_agent
    
    agent = create_supervisor_agent()
    response = stream_agent(agent, "What's wrong with the cluster?")
"""

__version__ = "1.0.0"

# Main API exports
from kube_medic.agents import create_supervisor_agent
from kube_medic.utils import ask_agent, stream_agent

__all__ = [
    "__version__",
    "create_supervisor_agent",
    "ask_agent",
    "stream_agent",
]