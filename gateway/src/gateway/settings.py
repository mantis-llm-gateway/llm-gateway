from functools import lru_cache

from pydantic import Field, model_validator
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

    # AWS / runtime
    aws_region: str = Field(default="us-east-1")
    log_level: str = Field(default="INFO")

    # Bedrock
    bedrock_guardrail_id: str | None = Field(default=None)
    bedrock_guardrail_version: str | None = Field(default=None)
    bedrock_embedding_model: str = Field(default="amazon.titan-embed-text-v2:0")
    bedrock_primary_chat_model: str | None = Field(default=None)

    @model_validator(mode="after")
    def _guardrail_version_requires_id(self) -> "Settings":
        if self.bedrock_guardrail_id is not None and self.bedrock_guardrail_version is None:
            raise ValueError(
                "bedrock_guardrail_version must be set when bedrock_guardrail_id is set"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
