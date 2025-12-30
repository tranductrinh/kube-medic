# KubeMedic

An AI-powered Kubernetes troubleshooting assistant built with LangChain.

## Features

- **Multi-Agent Architecture**: Supervisor coordinates specialist agents
- **Kubernetes**: Query pods, logs, events, and more
- **Prometheus**: Query metrics via PromQL (instant and range queries)
- **Conversation Memory**: Maintains context across questions

## Architecture

```
┌─────────────────────────────────────────┐
│          SUPERVISOR AGENT               │
│   (Routes questions to specialists)     │
│   (Has conversation memory)             │
└─────────────┬───────────────────────────┘
              │
    ┌─────────┴─────────┐
    ▼                   ▼
┌───────────┐     ┌──────────────┐
│    K8s    │     │  Prometheus  │
│   Agent   │     │   Agent      │
│           │     │              │
│ 11 tools  │     │ 2 tools      │
└───────────┘     └──────────────┘
```

### Kubernetes Agent Tools (READ-ONLY)

| Tool | Description |
|------|-------------|
| `get_events` | Get Kubernetes events (scheduling, crashes, etc.) |
| `get_node_details` | Get node capacity, conditions, and taints |
| `get_pod_details` | Get detailed information about a specific pod |
| `get_pod_logs` | Retrieve logs from a pod/container |
| `list_configmaps` | List ConfigMaps (keys only, not values) |
| `list_deployments` | List deployments with replica status |
| `list_namespaces` | List all namespaces in the cluster |
| `list_nodes` | List cluster nodes with status |
| `list_pods` | List pods with status and restart counts |
| `list_secrets` | List Secret names (not values) |
| `list_services` | List services with types and endpoints |

### Prometheus Agent Tools

| Tool | Description |
|------|-------------|
| `prometheus_query` | Execute PromQL instant queries |
| `prometheus_query_range` | Execute PromQL range queries for trend analysis |

## Prerequisites

- macOS (development tested)
- Python 3.9+
- Access to a Kubernetes cluster (kubeconfig or in-cluster)
- Prometheus instance
- Azure OpenAI API Key

## Installation

```bash
# Clone the repository
git clone https://github.com/tranductrinh/kube-medic.git
cd kube-medic

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac

# Install
pip install -e ".[dev]"
```

## Configuration

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
# Run interactive mode
python -m kube_medic.main
```

## Example Queries

```
"Check cluster health"
"What pods are running in the monitoring-system namespace?"
"Which pod has the most restarts?"
"Show me the logs for that pod"
"What's using the most CPU?"
"Are there any errors in the events?"
```

## Running Tests

```bash
# Unit tests only (default)
./run_tests.sh unit

# Integration tests (requires .env + services)
./run_tests.sh integration

# All tests
./run_tests.sh all

# With coverage report
./run_tests.sh coverage

