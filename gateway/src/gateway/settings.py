from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Infrastructure config loaded from environment.

    Locally: values come from .env via pydantic-settings.
    In Fargate: ECS injects env vars from Parameter Store; .env is absent.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Cache (Redis / Valkey)
    cache_endpoint: str = Field(default="localhost")
    cache_port: int = Field(default=6379)
    cache_auth_token: str | None = Field(default=None, repr=False)

    # Gateway runtime
    cooldown_ttl_seconds: int = Field(default=60)

    # AWS / runtime
    aws_region: str = Field(default="us-east-1")
    log_level: str = Field(default="INFO")


@lru_cache
def get_settings() -> Settings:
    return Settings()
