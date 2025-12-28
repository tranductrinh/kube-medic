# KubeMedic

An AI-powered Kubernetes troubleshooting assistant built with LangChain.

## Features

- **Multi-Agent Architecture**: Supervisor coordinates specialist agents
- **Kubernetes**: Query pods, logs, events, and more
- **Prometheus**: CPU, memory, restart counts, and health checks
- **Conversation Memory**: Maintains context across questions

## Architecture

```
┌─────────────────────────────────────────┐
│           SUPERVISOR AGENT              │
│   (Routes questions to specialists)     │
│   (Has conversation memory)             │
└─────────────┬───────────────────────────┘
              │
    ┌─────────┴─────────┐
    ▼                   ▼
┌───────────┐     ┌───────────┐
│    K8s    │     │  Metrics  │
│   Agent   │     │   Agent   │
│           │     │           │
│ 5 tools   │     │ 4 tools   │
└───────────┘     └───────────┘
```

## Prerequisites

- macOS (development tested)
- Python 3.9+
- Access to a Kubernetes cluster (kubeconfig or in-cluster)
- Prometheus instance
- Azure OpenAI API Key

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/tranductrinh/kube-medic.git
cd kube-medic

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

Required environment variables:

| Variable                       | Description                           |
|--------------------------------|---------------------------------------|
| `AZURE_OPENAI_ENDPOINT`        | Azure OpenAI endpoint URL             |
| `AZURE_OPENAI_API_KEY`         | Azure OpenAI API key                  |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Model deployment name (e.g., gpt-4.1) |
| `AZURE_OPENAI_API_VERSION`     | API version                           |
| `PROMETHEUS_URL`               | Prometheus server URL                 |

The program will exit if required variables are missing.

## Usage

```bash
python src/main.py
```
