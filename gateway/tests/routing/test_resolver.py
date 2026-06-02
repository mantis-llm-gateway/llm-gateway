import random

from gateway.models import (
    AliasConfig,
    Config,
    PromptCacheConfig,
    RoutingRuleConfig,
    RuleMatchConfig,
    SemanticCacheConfig,
    TargetConfig,
)
from gateway.routing import ResolvedTarget, resolve_attempt_chain


def make_config(**overrides) -> Config:
    base = Config(
        aliases={
            "model-a": AliasConfig(provider="anthropic", model="claude-3"),
            "model-b": AliasConfig(provider="openai", model="gpt-4"),
            "fallback": AliasConfig(provider="gemini", model="gemini-pro"),
        },
        routing_rules=[
            RoutingRuleConfig(
                id="1",
                name="code",
                match=RuleMatchConfig(name="task-type", value="code_generation"),
                targets=[
                    TargetConfig(alias="model-a", weight=1),
                    TargetConfig(alias="model-b", weight=1),
                ],
            ),
        ],
        target_retries=2,
        initial_response_timeout=30,
        stream_idle_timeout=10,
        default_model="model-a",
        fallbacks=["fallback"],
        cooldown_ttl=60,
        prompt_cache=PromptCacheConfig(
            ttl_seconds=60,
            temperature_threshold=0.3,
            semantic=SemanticCacheConfig(
                similarity_threshold=0.8,
                top_k=3,
                conversation_size_threshold=3,
            ),
        ),
    )
    if overrides:
        return base.model_copy(update=overrides)
    return base


class TestResolveAttemptChain:
    def test_empty_metadata_returns_default_plus_fallbacks(self):
        config = make_config()
        chain = resolve_attempt_chain({}, config)
        assert chain == [
            ResolvedTarget(provider="anthropic", model="claude-3"),
            ResolvedTarget(provider="gemini", model="gemini-pro"),
        ]

    def test_unmatched_metadata_returns_default_plus_fallbacks(self):
        config = make_config()
        chain = resolve_attempt_chain({"task-type": "unknown"}, config)
        assert chain == [
            ResolvedTarget(provider="anthropic", model="claude-3"),
            ResolvedTarget(provider="gemini", model="gemini-pro"),
        ]

    def test_matched_rule_uses_rule_targets_plus_fallbacks(self):
        config = make_config()
        chain = resolve_attempt_chain(
            {"task-type": "code_generation"}, config, rng=random.Random(42)
        )
        # First two come from the rule (in some weighted order), last is fallback.
        assert len(chain) == 3
        assert chain[-1] == ResolvedTarget(provider="gemini", model="gemini-pro")
        rule_targets = {
            ResolvedTarget(provider="anthropic", model="claude-3"),
            ResolvedTarget(provider="openai", model="gpt-4"),
        }
        assert set(chain[:2]) == rule_targets

    def test_weighted_selection_picks_heaviest(self):
        config = make_config(
            routing_rules=[
                RoutingRuleConfig(
                    id="1",
                    name="code",
                    match=RuleMatchConfig(name="task-type", value="code_generation"),
                    targets=[
                        TargetConfig(alias="model-a", weight=100),
                        TargetConfig(alias="model-b", weight=0),
                    ],
                ),
            ]
        )
        chain = resolve_attempt_chain(
            {"task-type": "code_generation"}, config, rng=random.Random(42)
        )
        assert chain[0] == ResolvedTarget(provider="anthropic", model="claude-3")
