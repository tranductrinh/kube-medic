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

    # Required settings (no defaults = must be set)
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
    try:
        settings = get_settings()
        print("Settings loaded!")
        print(f"   Endpoint: {settings.azure_openai_endpoint}")
        print(f"   Prometheus: {settings.prometheus_url}")
    except Exception as e:
        print(f"Error: {e}")
