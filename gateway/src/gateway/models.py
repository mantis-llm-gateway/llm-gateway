from pydantic import BaseModel


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
    id: str
    name: str
    match: RuleMatchConfig
    targets: list[TargetConfig]


class Config(BaseModel):
    aliases: dict[str, AliasConfig]
    routing_rules: list[RoutingRuleConfig]
    target_retries: int
    fallbacks: list[str]
    initial_response_timeout: int
    default_model: str
    cooldown_ttl: int
