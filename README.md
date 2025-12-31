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

See [TOOLS.md](TOOLS.md) for detailed tool documentation.

## Prerequisites

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

| Variable                       | Description                                 |
|--------------------------------|---------------------------------------------|
| `AZURE_OPENAI_ENDPOINT`        | Azure OpenAI endpoint URL                   |
| `AZURE_OPENAI_API_KEY`         | Azure OpenAI API key                        |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Model deployment name (e.g., gpt-4o)        |
| `PROMETHEUS_URL`               | Prometheus server URL                       |
| `SMTP_HOST`                    | SMTP server hostname (e.g., smtp.gmail.com) |
| `EMAIL_FROM`                   | Sender email address                        |
| `EMAIL_TO`                     | Recipient for all investigation reports     |

The server will fail to start if required variables are missing. See `.env.example` for all options.

## Usage

KubeMedic runs as a REST API server that accepts webhooks for automated incident investigation. The webhook endpoint
accepts any JSON payload and intelligently processes it.

### Running Locally

```bash
# Start the API server
kube-medic

# Or directly
python -m kube_medic.api
```

### Running with Docker

```bash
# Build the image
docker build -t kube-medic .

# Run with environment file and kubeconfig mounted
docker run -p 8000:8000 \
  --env-file .env \
  -v ~/.kube/config:/home/appuser/.kube/config:ro \
  kube-medic
```

> **Note:** The container runs as non-root user `appuser`. Mount kubeconfig to `/home/appuser/.kube/config`.

### API Endpoints

| Endpoint        | Method | Description                                                          |
|-----------------|--------|----------------------------------------------------------------------|
| `/health`       | GET    | Health check                                                         |
| `/webhook`      | POST   | Generic webhook (async, returns immediately with `{"status": "ok"}`) |
| `/webhook/sync` | POST   | Generic webhook (waits for agent response)                           |
| `/query`        | POST   | Direct agent query                                                   |

**Async vs Sync Webhooks:**

- `/webhook` (async): Returns immediately with `{"status": "ok"}`. The agent investigates in the background and sends
  results via email to `EMAIL_TO`.
- `/webhook/sync`: Blocks until investigation completes and returns the full response. Use for integrations that need
  immediate results.

**Query Parameters:**

- `question` (required): The question or issue to investigate
- `thread_id` (optional): Conversation identifier for maintaining context. Use the same `thread_id` to continue a
  conversation across multiple queries. Omit for stateless queries.

API documentation available at `http://localhost:8000/docs` (Swagger UI).

## Deployment

### In-Cluster Deployment

To deploy KubeMedic inside your Kubernetes cluster:

#### 1. Create RBAC Resources

```yaml
# rbac.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: kube-medic
  namespace: monitoring
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: kube-medic
rules:
  - apiGroups: [ "" ]
    resources: [ "pods", "pods/log", "services", "endpoints", "events", "nodes", "namespaces", "configmaps", "secrets" ]
    verbs: [ "get", "list" ]
  - apiGroups: [ "apps" ]
    resources: [ "deployments", "replicasets", "statefulsets", "daemonsets" ]
    verbs: [ "get", "list" ]
  - apiGroups: [ "networking.k8s.io" ]
    resources: [ "ingresses" ]
    verbs: [ "get", "list" ]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: kube-medic
subjects:
  - kind: ServiceAccount
    name: kube-medic
    namespace: monitoring
roleRef:
  kind: ClusterRole
  name: kube-medic
  apiGroup: rbac.authorization.k8s.io
```

#### 2. Create Secret for Environment Variables

```yaml
# secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: kube-medic
  namespace: monitoring
type: Opaque
stringData:
  AZURE_OPENAI_ENDPOINT: "https://your-resource.openai.azure.com/"
  AZURE_OPENAI_API_KEY: "your-api-key"
  AZURE_OPENAI_DEPLOYMENT_NAME: "gpt-4o"
  PROMETHEUS_URL: "http://prometheus-server.monitoring:80"
  SMTP_HOST: "smtp.gmail.com"
  EMAIL_FROM: "kube-medic@example.com"
  EMAIL_TO: "ops-team@example.com"
```

#### 3. Create Deployment and Service

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kube-medic
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: kube-medic
  template:
    metadata:
      labels:
        app: kube-medic
    spec:
      serviceAccountName: kube-medic
      containers:
        - name: kube-medic
          image: kube-medic:latest
          ports:
            - containerPort: 8000
          envFrom:
            - secretRef:
                name: kube-medic
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: kube-medic
  namespace: monitoring
spec:
  selector:
    app: kube-medic
  ports:
    - port: 8000
      targetPort: 8000
```

#### 4. Apply Resources

```bash
kubectl apply -f rbac.yaml
kubectl apply -f secret.yaml
kubectl apply -f deployment.yaml
```

### Alertmanager Integration

KubeMedic can receive alerts directly from Prometheus Alertmanager. Add a receiver to your `alertmanager.yml`:

```yaml
receivers:
  - name: 'kube-medic'
    webhook_configs:
      - url: 'http://kube-medic.monitoring:8000/webhook'
        send_resolved: false  # Optional: don't notify on resolution

route:
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'kube-medic'
```

When an alert fires, KubeMedic will:

1. Parse the alert payload (labels, annotations, status)
2. Investigate using Kubernetes and Prometheus data
3. Send a detailed analysis via email to `EMAIL_TO`

## Development

### Running Tests

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
