from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AliasConfig(BaseModel):
    provider: str
    model: str


class RuleMatchConfig(BaseModel):
    name: str
    value: str


class TargetConfig(BaseModel):
    alias: str
    weight: int


class RoutingRuleConfig(BaseModel):
    id: str | None = None
    name: str
    match: RuleMatchConfig
    targets: list[TargetConfig]


class SemanticCacheConfig(BaseModel):
    similarity_threshold: float
    top_k: int
    conversation_size_threshold: int


class PromptCacheConfig(BaseModel):
    ttl_seconds: int
    temperature_threshold: float
    semantic: SemanticCacheConfig | None = None


class Config(BaseModel):
    aliases: dict[str, AliasConfig]
    routing_rules: list[RoutingRuleConfig]
    target_retries: int
    fallbacks: list[str]
    initial_response_timeout: int
    default_model: str
    cooldown_ttl: int
    prompt_cache: PromptCacheConfig


class ConfigResponse(BaseModel):
    config: Config
    reload_required: bool


class ChatMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: NonEmptyString


class ChatCompletionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[ChatMessageRequest] = Field(min_length=1)
    stream: bool = False
