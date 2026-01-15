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
    azure_openai_endpoint: str = Field(
        ...,
        description="Azure OpenAI endpoint URL",
    )
    azure_openai_api_key: str = Field(
        ...,
        description="Azure OpenAI API key",
    )
    azure_openai_deployment_name: str = Field(
        ...,
        description="Azure OpenAI deployment name",
    )
    prometheus_url: str = Field(
        ...,
        description="Prometheus server URL",
    )

    # =========================================================================
    # LLM CONFIGURATION
    # =========================================================================
    azure_openai_api_version: str = Field(
        default="2024-08-01-preview",
        description="Azure OpenAI API version",
    )
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

    @field_validator("prometheus_url", "azure_openai_endpoint")
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
        logger.info(f"Endpoint: {settings.azure_openai_endpoint}")
        logger.info(f"Prometheus: {settings.prometheus_url}")
    except Exception as e:
        logger.error(f"Error: {e}")
