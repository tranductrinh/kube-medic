"""
FastAPI REST API for KubeMedic.

Exposes the supervisor agent via HTTP endpoints, including
webhook integration for automated incident response.
"""

import asyncio
import hashlib
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from kube_medic.agents import create_supervisor_agent
from kube_medic.config import get_settings
from kube_medic.logging_config import get_logger, setup_logging
from kube_medic.utils.helpers import ask_agent

logger = get_logger(__name__)


# =============================================================================
# RESPONSE MODELS
# =============================================================================


class WebhookResponse(BaseModel):
    """Response for webhook processing."""

    status: str


class QueryRequest(BaseModel):
    """Direct query request."""

    question: str = Field(..., min_length=1, description="Question to ask the agent")
    thread_id: str = Field(default="default", description="Conversation thread ID")


class QueryResponse(BaseModel):
    """Response from agent query."""

    response: str
    thread_id: str


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    agent_ready: bool


# =============================================================================
# APP STATE
# =============================================================================


class AppState:
    """Application state container."""

    def __init__(self):
        self.agent = None
        self.processing_lock = asyncio.Lock()


app_state = AppState()


# =============================================================================
# LIFESPAN MANAGEMENT
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - initialize agent on startup."""
    # Setup logging based on api_log_level setting
    settings = get_settings()
    log_level = logging.getLevelName(settings.api_log_level.upper())
    setup_logging(level=log_level)

    logger.info("Starting KubeMedic API server...")

    # Initialize the supervisor agent
    logger.info("Initializing supervisor agent...")
    app_state.agent = create_supervisor_agent(use_memory=True)
    logger.info("Supervisor agent initialized successfully")

    yield

    # Cleanup
    logger.info("Shutting down KubeMedic API server...")
    app_state.agent = None


# =============================================================================
# FASTAPI APP
# =============================================================================


app = FastAPI(
    title="KubeMedic API",
    description="AI-powered Kubernetes troubleshooting agent with webhook integration",
    version="1.0.0",
    lifespan=lifespan,
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def generate_thread_id(payload: dict[str, Any]) -> str:
    """Generate a deterministic thread ID from payload content."""
    payload_str = json.dumps(payload, sort_keys=True, default=str)
    return f"webhook-{hashlib.md5(payload_str.encode()).hexdigest()[:12]}"


def format_payload_as_query(payload: dict[str, Any]) -> str:
    """
    Convert any webhook payload into a natural language query.

    Intelligently formats the payload based on its structure,
    with special handling for Alertmanager format.

    Args:
        payload: The webhook payload (any JSON structure)

    Returns:
        A formatted query string for the agent
    """
    # Detect Alertmanager format
    if "alerts" in payload and isinstance(payload.get("alerts"), list):
        logger.debug("Detected Alertmanager payload format")
        return _format_alertmanager_payload(payload)

    # Generic payload - format as structured investigation request
    logger.debug(f"Processing generic payload with {len(payload)} keys: {list(payload.keys())}")
    payload_formatted = json.dumps(payload, indent=2, default=str)

    return f"""A webhook has been received that requires investigation:

```json
{payload_formatted}
```

Please analyze this data and investigate any issues indicated. Find the root cause and suggest remediation steps."""


def _format_alertmanager_payload(payload: dict[str, Any]) -> str:
    """Format Alertmanager-style payload."""
    alerts = payload.get("alerts", [])
    firing_alerts = [a for a in alerts if a.get("status") == "firing"]
    resolved_alerts = [a for a in alerts if a.get("status") == "resolved"]

    logger.debug(
        f"Alertmanager payload: {len(alerts)} total alerts, "
        f"{len(firing_alerts)} firing, {len(resolved_alerts)} resolved"
    )

    if not firing_alerts:
        logger.info("No firing alerts in payload, skipping processing")
        return ""

    if len(firing_alerts) == 1:
        alert = firing_alerts[0]
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})

        alertname = labels.get("alertname", "Unknown Alert")
        severity = labels.get("severity", "unknown")
        namespace = labels.get("namespace", "")
        pod = labels.get("pod", "")
        service = labels.get("service", "")

        logger.info(
            f"Processing single alert: {alertname} "
            f"(severity={severity}, namespace={namespace or 'cluster-wide'})"
        )

        description = annotations.get(
            "description",
            annotations.get("summary", "No description provided"),
        )

        context_parts = []
        if namespace:
            context_parts.append(f"namespace={namespace}")
        if pod:
            context_parts.append(f"pod={pod}")
        if service:
            context_parts.append(f"service={service}")

        context = ", ".join(context_parts) if context_parts else "cluster-wide"

        return f"""An alert has fired and needs investigation:

Alert: {alertname}
Severity: {severity}
Context: {context}

Description: {description}

Please investigate this alert. Find the root cause and suggest remediation steps."""

    # Multiple alerts
    alert_names = [a.get("labels", {}).get("alertname", "Unknown") for a in firing_alerts]
    logger.info(f"Processing {len(firing_alerts)} alerts: {', '.join(alert_names)}")

    alert_summaries = []
    for alert in firing_alerts:
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        alertname = labels.get("alertname", "Unknown")
        severity = labels.get("severity", "unknown")
        namespace = labels.get("namespace", "default")
        description = annotations.get("description", annotations.get("summary", ""))
        alert_summaries.append(
            f"- {alertname} (severity={severity}, namespace={namespace}): {description}"
        )

    alerts_text = "\n".join(alert_summaries)

    return f"""Multiple alerts have fired and need investigation:

Total firing alerts: {len(firing_alerts)}

Alerts:
{alerts_text}

Please investigate these alerts together. They may be related. Find the root cause and suggest remediation steps."""


def process_payload_background(payload: dict[str, Any], thread_id: str) -> None:
    """
    Process webhook payload in background (fire-and-forget).

    Args:
        payload: The webhook payload
        thread_id: Thread ID for conversation context
    """
    logger.debug(f"[{thread_id}] Starting background processing")
    start_time = time.time()

    query = format_payload_as_query(payload)
    if not query:
        logger.info(f"[{thread_id}] No actionable content in webhook payload, skipping")
        return

    logger.info(f"[{thread_id}] Invoking agent for investigation...")
    logger.debug(f"[{thread_id}] Query length: {len(query)} chars")

    try:
        response = ask_agent(app_state.agent, query, thread_id)
        elapsed = time.time() - start_time
        logger.info(
            f"[{thread_id}] Investigation complete in {elapsed:.2f}s, "
            f"response length: {len(response)} chars"
        )
        logger.debug(f"[{thread_id}] Response preview: {response[:300]}...")
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[{thread_id}] Investigation failed after {elapsed:.2f}s: {e}")


# =============================================================================
# ENDPOINTS
# =============================================================================


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    agent_ready = app_state.agent is not None
    logger.debug(f"Health check: agent_ready={agent_ready}")
    return HealthResponse(
        status="healthy",
        agent_ready=agent_ready,
    )


@app.post("/webhook", response_model=WebhookResponse)
async def webhook(
        payload: dict[str, Any],
        background_tasks: BackgroundTasks,
) -> WebhookResponse:
    """
    Receive any webhook payload and trigger investigation.

    This endpoint accepts any JSON payload and processes it in the background.
    Returns immediately with "ok" status.

    Works with:
    - Alertmanager webhooks (auto-detected and formatted nicely)
    - Custom monitoring systems
    - Any JSON payload describing an issue to investigate

    Example Alertmanager config:
    ```yaml
    receivers:
      - name: 'kube-medic'
        webhook_configs:
          - url: 'http://kube-medic:8000/webhook'
    ```
    """
    if app_state.agent is None:
        logger.warning("Webhook received but agent not initialized")
        raise HTTPException(status_code=503, detail="Agent not initialized")

    thread_id = generate_thread_id(payload)

    # Determine payload type for logging
    if "alerts" in payload and isinstance(payload.get("alerts"), list):
        alert_count = len(payload["alerts"])
        firing = sum(1 for a in payload["alerts"] if a.get("status") == "firing")
        logger.info(
            f"[{thread_id}] Received Alertmanager webhook: "
            f"{alert_count} alerts ({firing} firing)"
        )
    else:
        logger.info(f"[{thread_id}] Received generic webhook with keys: {list(payload.keys())}")

    # Process in background
    background_tasks.add_task(process_payload_background, payload, thread_id)
    logger.debug(f"[{thread_id}] Queued for background processing")

    return WebhookResponse(status="ok")


@app.post("/webhook/sync", response_model=QueryResponse)
async def webhook_sync(payload: dict[str, Any]) -> QueryResponse:
    """
    Receive any webhook payload and process synchronously.

    This endpoint waits for the agent to complete investigation before
    returning. Use this for testing or when you need the response immediately.

    Note: May timeout for complex investigations. For production, use /webhook.
    """
    if app_state.agent is None:
        logger.warning("Sync webhook received but agent not initialized")
        raise HTTPException(status_code=503, detail="Agent not initialized")

    thread_id = generate_thread_id(payload)
    logger.info(f"[{thread_id}] Received sync webhook request")

    query = format_payload_as_query(payload)

    if not query:
        logger.info(f"[{thread_id}] No actionable content in payload")
        return QueryResponse(
            response="No actionable content in payload",
            thread_id=thread_id,
        )

    logger.info(f"[{thread_id}] Processing synchronously...")
    start_time = time.time()

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        ask_agent,
        app_state.agent,
        query,
        thread_id,
    )

    elapsed = time.time() - start_time
    logger.info(
        f"[{thread_id}] Sync processing complete in {elapsed:.2f}s, "
        f"response length: {len(response)} chars"
    )

    return QueryResponse(response=response, thread_id=thread_id)


@app.post("/query", response_model=QueryResponse)
async def query_agent(request: QueryRequest) -> QueryResponse:
    """
    Send a direct query to the supervisor agent.

    This endpoint allows direct interaction with the agent outside of
    webhooks. Useful for ad-hoc investigations.
    """
    if app_state.agent is None:
        logger.warning("Query received but agent not initialized")
        raise HTTPException(status_code=503, detail="Agent not initialized")

    thread_id = request.thread_id
    question_preview = request.question[:80] + "..." if len(request.question) > 80 else request.question
    logger.info(f"[{thread_id}] Received query: {question_preview}")
    logger.debug(f"[{thread_id}] Full question length: {len(request.question)} chars")

    start_time = time.time()

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        ask_agent,
        app_state.agent,
        request.question,
        request.thread_id,
    )

    elapsed = time.time() - start_time
    logger.info(
        f"[{thread_id}] Query complete in {elapsed:.2f}s, "
        f"response length: {len(response)} chars"
    )

    return QueryResponse(response=response, thread_id=request.thread_id)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def main() -> None:
    """Run the API server."""
    settings = get_settings()
    logger.info(f"Starting KubeMedic API on {settings.api_host}:{settings.api_port}...")
    uvicorn.run(
        "kube_medic.api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.api_log_level,
    )


if __name__ == "__main__":
    main()
