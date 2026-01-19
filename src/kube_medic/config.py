"""
Configuration management using Pydantic Settings.

Loads required environment variables with validation.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =========================================================================
    # REQUIRED SETTINGS (no defaults = must be set)
    # =========================================================================
    openai_base_url: str = Field(
        ...,
        description="OpenAI-compatible API base URL (e.g., https://your-resource.openai.azure.com/openai/v1/)",
    )
    openai_api_key: str = Field(
        ...,
        description="OpenAI API key",
    )
    openai_model: str = Field(
        ...,
        description="Model/deployment name (e.g., gpt-5.2, gpt-4o)",
    )
    prometheus_url: str = Field(
        ...,
        description="Prometheus server URL",
    )

    # =========================================================================
    # LLM CONFIGURATION
    # =========================================================================
    llm_temperature: float = Field(
        default=0.0,
        description="LLM temperature for response generation (0=deterministic, 1=creative)",
        ge=0.0,
        le=2.0,
    )
    llm_max_tokens: int = Field(
        default=2048,
        description="Maximum tokens in LLM response",
        gt=0,
    )

    # =========================================================================
    # PROMETHEUS CONFIGURATION
    # =========================================================================
    prometheus_username: str = Field(
        default="",
        description="Prometheus basic auth username (optional)",
    )
    prometheus_password: str = Field(
        default="",
        description="Prometheus basic auth password (optional)",
    )
    prometheus_timeout: int = Field(
        default=10,
        description="Timeout in seconds for Prometheus API requests",
        gt=0,
    )
    prometheus_max_series_results: int = Field(
        default=20,
        description="Maximum number of time series to return from Prometheus queries",
        gt=0,
    )

    # =========================================================================
    # KUBERNETES CONFIGURATION
    # =========================================================================
    k8s_logs_tail_lines: int = Field(
        default=300,
        description="Number of log lines to retrieve from pod logs",
        gt=0,
    )
    k8s_logs_max_chars: int = Field(
        default=40000,
        description="Maximum characters to keep when truncating pod logs",
        gt=0,
    )

    # =========================================================================
    # TEXT FORMATTING
    # =========================================================================
    text_truncate_max_length: int = Field(
        default=500,
        description="Default maximum length for text truncation",
        gt=0,
    )

    # =========================================================================
    # AGENT CONFIGURATION
    # =========================================================================
    agent_recursion_limit: int = Field(
        default=50,
        description="Maximum recursion depth for agent tool calls",
        gt=0,
    )

    # =========================================================================
    # MEMORY CONFIGURATION
    # =========================================================================
    memory_max_threads: int = Field(
        default=1000,
        description="Maximum number of conversation threads to keep in memory",
        gt=0,
    )
    memory_ttl_seconds: int = Field(
        default=3600,
        description="Time-to-live in seconds for conversation memory (default: 1 hour)",
        gt=0,
    )

    # =========================================================================
    # RATE LIMITING CONFIGURATION
    # =========================================================================
    rate_limit_webhook: str = Field(
        default="30/minute",
        description="Rate limit for webhook endpoint (requests per time period)",
    )
    rate_limit_query: str = Field(
        default="10/minute",
        description="Rate limit for query endpoint (requests per time period)",
    )

    # =========================================================================
    # CACHING CONFIGURATION
    # =========================================================================
    cache_prometheus_ttl: int = Field(
        default=60,
        description="TTL in seconds for Prometheus query cache",
        gt=0,
    )
    cache_prometheus_maxsize: int = Field(
        default=100,
        description="Maximum number of Prometheus queries to cache",
        gt=0,
    )
    cache_k8s_ttl: int = Field(
        default=30,
        description="TTL in seconds for Kubernetes API cache (shorter due to dynamic nature)",
        gt=0,
    )
    cache_k8s_maxsize: int = Field(
        default=200,
        description="Maximum number of Kubernetes API calls to cache",
        gt=0,
    )

    # =========================================================================
    # RETRY CONFIGURATION
    # =========================================================================
    webhook_max_retries: int = Field(
        default=3,
        description="Maximum number of retries for failed webhook processing",
        gt=0,
    )
    webhook_retry_min_wait: int = Field(
        default=2,
        description="Minimum wait time in seconds between retries",
        gt=0,
    )
    webhook_retry_max_wait: int = Field(
        default=30,
        description="Maximum wait time in seconds between retries",
        gt=0,
    )

    # =========================================================================
    # API SERVER CONFIGURATION
    # =========================================================================
    api_host: str = Field(
        default="0.0.0.0",
        description="Host to bind the API server to",
    )
    api_port: int = Field(
        default=8000,
        description="Port to run the API server on",
        gt=0,
        le=65535,
    )
    api_log_level: str = Field(
        default="info",
        description="Log level for the API server (debug, info, warning, error, critical)",
    )

    # =========================================================================
    # EMAIL CONFIGURATION (Required - for email notifications)
    # =========================================================================
    smtp_host: str = Field(
        ...,
        description="SMTP server hostname",
    )
    smtp_port: int = Field(
        default=587,
        description="SMTP server port",
        gt=0,
        le=65535,
    )
    smtp_username: str = Field(
        default="",
        description="SMTP authentication username (optional)",
    )
    smtp_password: str = Field(
        default="",
        description="SMTP authentication password (optional)",
    )
    smtp_use_tls: bool = Field(
        default=True,
        description="Use TLS for SMTP connection",
    )
    email_from: str = Field(
        ...,
        description="Sender email address",
    )
    email_to: str = Field(
        ...,
        description="Recipient email address for all notifications",
    )

    @field_validator("prometheus_url", "openai_base_url")
    @classmethod
    def remove_trailing_slash(cls, v: str) -> str:
        """Remove trailing slashes from URLs."""
        return v.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Quick test
if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    try:
        settings = get_settings()
        logger.info("Settings loaded!")
        logger.info(f"Base URL: {settings.openai_base_url}")
        logger.info(f"Model: {settings.openai_model}")
        logger.info(f"Prometheus: {settings.prometheus_url}")
    except Exception as e:
        logger.error(f"Error: {e}")
