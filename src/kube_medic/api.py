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
from datetime import datetime
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from kube_medic.agents import create_supervisor_agent
from kube_medic.config import get_settings
from kube_medic.logging_config import get_logger, setup_logging
from kube_medic.utils.helpers import ask_agent, get_recursion_stats

logger = get_logger(__name__)

# =============================================================================
# RATE LIMITER
# =============================================================================

limiter = Limiter(key_func=get_remote_address)


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


class FailedWebhook(BaseModel):
    """Record of a failed webhook processing attempt."""
    thread_id: str
    payload: dict[str, Any]
    error: str
    timestamp: str
    retry_count: int


class AppState:
    """Application state container."""

    def __init__(self):
        self.agent = None
        self.processing_lock = asyncio.Lock()
        self.failed_webhooks: list[FailedWebhook] = []  # Dead letter queue
        self.failed_webhooks_lock = asyncio.Lock()
        self.webhook_stats = {
            "total_received": 0,
            "total_success": 0,
            "total_failed": 0,
        }


app_state = AppState()


# =============================================================================
# RETRY HELPER
# =============================================================================

def _create_retry_decorator():
    """Create a retry decorator with settings from config."""
    settings = get_settings()
    return retry(
        stop=stop_after_attempt(settings.webhook_max_retries),
        wait=wait_exponential(
            multiplier=1,
            min=settings.webhook_retry_min_wait,
            max=settings.webhook_retry_max_wait,
        ),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )


def invoke_agent_with_retry(agent, query: str, thread_id: str) -> str:
    """Invoke agent with retry logic."""
    settings = get_settings()

    @retry(
        stop=stop_after_attempt(settings.webhook_max_retries),
        wait=wait_exponential(
            multiplier=1,
            min=settings.webhook_retry_min_wait,
            max=settings.webhook_retry_max_wait,
        ),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def _invoke():
        return ask_agent(agent, query, thread_id)

    return _invoke()


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

# Add rate limiting to the app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


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
    Process webhook payload in background with retry logic and dead letter queue.

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

    settings = get_settings()

    try:
        # Use retry logic for resilience
        response = invoke_agent_with_retry(app_state.agent, query, thread_id)
        elapsed = time.time() - start_time
        logger.info(
            f"[{thread_id}] Investigation complete in {elapsed:.2f}s, "
            f"response length: {len(response)} chars"
        )
        logger.debug(f"[{thread_id}] Response preview: {response[:300]}...")
        app_state.webhook_stats["total_success"] += 1

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(
            f"[{thread_id}] Investigation failed after {elapsed:.2f}s "
            f"and {settings.webhook_max_retries} retries: {e}"
        )
        app_state.webhook_stats["total_failed"] += 1

        # Add to dead letter queue
        failed_entry = FailedWebhook(
            thread_id=thread_id,
            payload=payload,
            error=str(e),
            timestamp=datetime.utcnow().isoformat(),
            retry_count=settings.webhook_max_retries,
        )

        # Use a simple list append (thread-safe for append in CPython)
        app_state.failed_webhooks.append(failed_entry)

        # Keep only last 100 failures to prevent memory growth
        if len(app_state.failed_webhooks) > 100:
            app_state.failed_webhooks = app_state.failed_webhooks[-100:]

        logger.warning(
            f"[{thread_id}] Added to dead letter queue. "
            f"Total failed: {len(app_state.failed_webhooks)}"
        )


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
@limiter.limit(lambda: get_settings().rate_limit_webhook)
async def webhook(
        request: Request,
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

    # Track webhook stats
    app_state.webhook_stats["total_received"] += 1

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
@limiter.limit(lambda: get_settings().rate_limit_webhook)
async def webhook_sync(request: Request, payload: dict[str, Any]) -> QueryResponse:
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
@limiter.limit(lambda: get_settings().rate_limit_query)
async def query_agent(request: Request, query_request: QueryRequest) -> QueryResponse:
    """
    Send a direct query to the supervisor agent.

    This endpoint allows direct interaction with the agent outside of
    webhooks. Useful for ad-hoc investigations.
    """
    if app_state.agent is None:
        logger.warning("Query received but agent not initialized")
        raise HTTPException(status_code=503, detail="Agent not initialized")

    thread_id = query_request.thread_id
    question_preview = query_request.question[:80] + "..." if len(query_request.question) > 80 else query_request.question
    logger.info(f"[{thread_id}] Received query: {question_preview}")
    logger.debug(f"[{thread_id}] Full question length: {len(query_request.question)} chars")

    start_time = time.time()

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        ask_agent,
        app_state.agent,
        query_request.question,
        query_request.thread_id,
    )

    elapsed = time.time() - start_time
    logger.info(
        f"[{thread_id}] Query complete in {elapsed:.2f}s, "
        f"response length: {len(response)} chars"
    )

    return QueryResponse(response=response, thread_id=query_request.thread_id)


# =============================================================================
# ADMIN ENDPOINTS
# =============================================================================


class AdminStatsResponse(BaseModel):
    """Response for admin statistics."""
    webhook_stats: dict[str, int]
    failed_webhook_count: int
    memory_stats: dict[str, Any] | None
    recursion_stats: dict[str, Any]


class FailedWebhooksResponse(BaseModel):
    """Response for failed webhooks endpoint."""
    count: int
    failures: list[FailedWebhook]


@app.get("/admin/stats", response_model=AdminStatsResponse)
async def get_admin_stats() -> AdminStatsResponse:
    """
    Get system statistics for monitoring.

    Returns webhook processing stats, memory usage, and recursion limit hits.
    """
    # Get memory stats from supervisor agent's checkpointer if available
    memory_stats = None
    if app_state.agent is not None:
        try:
            # Try to access the checkpointer's stats method
            checkpointer = getattr(app_state.agent, 'checkpointer', None)
            if checkpointer and hasattr(checkpointer, 'get_stats'):
                memory_stats = checkpointer.get_stats()
        except Exception as e:
            logger.debug(f"Could not get memory stats: {e}")

    return AdminStatsResponse(
        webhook_stats=app_state.webhook_stats,
        failed_webhook_count=len(app_state.failed_webhooks),
        memory_stats=memory_stats,
        recursion_stats=get_recursion_stats(),
    )


@app.get("/admin/failed-webhooks", response_model=FailedWebhooksResponse)
async def get_failed_webhooks() -> FailedWebhooksResponse:
    """
    View failed webhook processing attempts (dead letter queue).

    Returns the list of webhooks that failed after all retries.
    """
    return FailedWebhooksResponse(
        count=len(app_state.failed_webhooks),
        failures=app_state.failed_webhooks,
    )


@app.delete("/admin/failed-webhooks")
async def clear_failed_webhooks() -> dict[str, str]:
    """
    Clear the dead letter queue.

    Use this after investigating and addressing failed webhooks.
    """
    count = len(app_state.failed_webhooks)
    app_state.failed_webhooks.clear()
    logger.info(f"Cleared {count} failed webhooks from dead letter queue")
    return {"status": "ok", "cleared": str(count)}


@app.post("/admin/retry-webhook/{index}")
async def retry_failed_webhook(
    index: int,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """
    Retry a specific failed webhook by its index in the dead letter queue.

    Args:
        index: Index of the failed webhook to retry (0-based)
    """
    if index < 0 or index >= len(app_state.failed_webhooks):
        raise HTTPException(status_code=404, detail="Failed webhook not found")

    failed = app_state.failed_webhooks[index]

    # Remove from dead letter queue
    app_state.failed_webhooks.pop(index)

    # Requeue for processing
    background_tasks.add_task(
        process_payload_background,
        failed.payload,
        failed.thread_id,
    )

    logger.info(f"Retrying failed webhook {failed.thread_id}")
    return {"status": "ok", "thread_id": failed.thread_id}


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
