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

### Cluster Health & Overview
```
"Check overall cluster health"
"Are all nodes healthy?"
"Show me the cluster namespaces"
```

### Pod Troubleshooting
```
"What pods are crashing in the default namespace?"
"Show me pods with high restart counts"
"Get the logs for pod nginx-abc123 in production"
"Why is my pod stuck in Pending state?"
```

### Resource Usage (Prometheus)
```
"Which pods are using the most CPU right now?"
"Show memory usage trends for the last hour"
"Are there any pods near their resource limits?"
"What's the CPU usage trend for the monitoring namespace?"
```

### Deployments & Services
```
"List all deployments and their replica status"
"Are all deployments healthy?"
"Show me the services in kube-system namespace"
```

### Events & Debugging
```
"Are there any warning events in the cluster?"
"Show recent events for pod my-app-xyz"
"What scheduling issues are happening?"
```

### Nodes
```
"Show node capacity and allocatable resources"
"Are there any node conditions I should worry about?"
"Which nodes have taints?"
```

### Configuration
```
"List ConfigMaps in the default namespace"
"What secrets exist in production?"
```

### Multi-Step Investigation (uses conversation memory)
```
"Which namespace has the most pod restarts?"
"Show me the events for that namespace"
"Get logs from the pod with most restarts"
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

