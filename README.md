# KubeMedic

An AI-powered Kubernetes troubleshooting assistant built with LangChain.

## Features

- **Multi-Agent Architecture**: Supervisor coordinates specialist agents
- **Kubernetes**: Query pods, logs, events, ingresses, and more
- **Prometheus**: Query metrics via PromQL (instant and range queries)
- **Network**: HTTP connectivity checks for ingress/endpoint verification
- **Email**: Send investigation results and alerts via email
- **Conversation Memory**: Maintains context across questions
- **REST API**: FastAPI server with generic webhook support (compatible with Alertmanager and custom systems)

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                 SUPERVISOR AGENT                     │
│        (Routes questions to specialists)             │
│           (Has conversation memory)                  │
└────────────────────────┬────────────────────────────┘
                         │
       ┌─────────────┬───┴───┬─────────────┐
       ▼             ▼       ▼             ▼
  ┌─────────┐   ┌─────────┐ ┌─────────┐ ┌─────────┐
  │   K8s   │   │  Prom   │ │ Network │ │  Email  │
  │  Agent  │   │  Agent  │ │  Agent  │ │  Agent  │
  │         │   │         │ │         │ │         │
  │12 tools │   │ 2 tools │ │ 1 tool  │ │ 1 tool  │
  └─────────┘   └─────────┘ └─────────┘ └─────────┘
```

### Kubernetes Agent Tools (READ-ONLY)

| Tool               | Description                                       |
|--------------------|---------------------------------------------------|
| `get_events`       | Get Kubernetes events (scheduling, crashes, etc.) |
| `get_node_details` | Get node capacity, conditions, and taints         |
| `get_pod_details`  | Get detailed information about a specific pod     |
| `get_pod_logs`     | Retrieve logs from a pod/container                |
| `list_configmaps`  | List ConfigMaps (keys only, not values)           |
| `list_deployments` | List deployments with replica status              |
| `list_ingresses`   | List ingresses with routing rules and backends    |
| `list_namespaces`  | List all namespaces in the cluster                |
| `list_nodes`       | List cluster nodes with status                    |
| `list_pods`        | List pods with status and restart counts          |
| `list_secrets`     | List Secret names (not values)                    |
| `list_services`    | List services with types and endpoints            |

### Prometheus Agent Tools

| Tool                     | Description                                     |
|--------------------------|-------------------------------------------------|
| `prometheus_query`       | Execute PromQL instant queries                  |
| `prometheus_query_range` | Execute PromQL range queries for trend analysis |

### Network Agent Tools

| Tool         | Description                                                                     |
|--------------|---------------------------------------------------------------------------------|
| `http_check` | Check HTTP/HTTPS endpoint accessibility (status code, response time, redirects) |

### Email Agent Tools

| Tool         | Description                                         |
|--------------|-----------------------------------------------------|
| `send_email` | Send email notifications with investigation results |

## Prerequisites

- macOS (development tested)
- Python 3.12+
- Access to a Kubernetes cluster (kubeconfig or in-cluster)
- Prometheus instance
- Azure OpenAI API access
- SMTP server for email notifications

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

| Variable                       | Description                              |
|--------------------------------|------------------------------------------|
| `AZURE_OPENAI_ENDPOINT`        | Azure OpenAI endpoint URL                |
| `AZURE_OPENAI_API_KEY`         | Azure OpenAI API key                     |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Model deployment name (e.g., gpt-4o)     |
| `PROMETHEUS_URL`               | Prometheus server URL                    |
| `SMTP_HOST`                    | SMTP server hostname (e.g., smtp.gmail.com) |
| `EMAIL_FROM`                   | Sender email address                     |
| `EMAIL_TO`                     | Recipient for all investigation reports  |

The server will fail to start if required variables are missing. See `.env.example` for all options.

## Usage

KubeMedic runs as a REST API server that accepts webhooks for automated incident investigation. The webhook endpoint
accepts any JSON payload and intelligently processes it.

```bash
# Start the API server
kube-medic

# Or directly
python -m kube_medic.api
```

### API Endpoints

| Endpoint        | Method | Description                                                          |
|-----------------|--------|----------------------------------------------------------------------|
| `/health`       | GET    | Health check                                                         |
| `/webhook`      | POST   | Generic webhook (async, returns immediately with `{"status": "ok"}`) |
| `/webhook/sync` | POST   | Generic webhook (waits for agent response)                           |
| `/query`        | POST   | Direct agent query                                                   |

API documentation available at `http://localhost:8000/docs` (Swagger UI).

### API Examples

```bash
# Health check
curl http://localhost:8000/health

# Direct query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Why is my pod crashing?", "thread_id": "user-123"}'

# Generic webhook (any JSON)
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"issue": "High latency detected", "service": "api-gateway", "p99_ms": 2500}'

# Alertmanager webhook
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "status": "firing",
    "alerts": [{
      "status": "firing",
      "labels": {
        "alertname": "HighMemoryUsage",
        "namespace": "production",
        "pod": "my-app-xyz",
        "severity": "warning"
      },
      "annotations": {
        "description": "Pod memory usage exceeds 90%"
      }
    }]
  }'

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
```
