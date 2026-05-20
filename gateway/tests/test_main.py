import random

import pytest

from gateway.main import (
    RoutingRuleConfig,
    TargetConfig,
    TargetCostConfig,
    build_attempt_chain,
    is_matching_rule,
    select_entry_target,
    sort_cost_map,
)
from gateway.models import AliasConfig, Config, CostBasedRoutingConfig, RuleMatchConfig
from gateway.validation import validate_no_duplicates_in_config

FAKE_ALIASES = {
    "model-a": AliasConfig(provider="anthropic", model="claude-3"),
    "model-b": AliasConfig(provider="openai", model="gpt-4"),
    "model-c": AliasConfig(provider="gemini", model="gemini-pro"),
}


def make_rule(name: str, aliases: list[str]) -> RoutingRuleConfig:
    return RoutingRuleConfig(
        id="1",
        name=name,
        match=RuleMatchConfig(name="task-type", value="test"),
        targets=[TargetConfig(alias=alias, weight=1) for alias in aliases],
    )


def make_config(
    rules: list[RoutingRuleConfig], fallbacks: list[str], aliases: dict | None = None
) -> Config:
    return Config(
        aliases=aliases if aliases is not None else FAKE_ALIASES,
        routing_rules=rules,
        target_retries=3,
        fallbacks=fallbacks,
        initial_response_timeout=30,
        default_model="model-a",
        cooldown_ttl=60,
        cost_based_routing=CostBasedRoutingConfig(enabled=False, cost_map=[]),
    )


# From Hubert's review for PR 9: Do you also have a test where target A is in cooldown,
# target B is tried and all targets in cooldown return no usable target?
# I guess that should probably wait until you have implemented the cooldown write path though.

# Don't forget to add the test above.


class TestCheckForDuplicatesInConfig:
    def test_no_duplicates_passes(self):
        rules = [make_rule("rule-1", ["model-a", "model-b"])]
        validate_no_duplicates_in_config(make_config(rules, fallbacks=["model-c"]))

    def test_duplicate_within_targets_raises(self):
        rules = [make_rule("rule-1", ["model-a", "model-a"])]
        with pytest.raises(ValueError, match="rule-1"):
            validate_no_duplicates_in_config(make_config(rules, fallbacks=[]))

    def test_duplicate_between_targets_and_fallbacks_raises(self):
        rules = [make_rule("rule-1", ["model-a", "model-b"])]
        with pytest.raises(ValueError, match="rule-1"):
            validate_no_duplicates_in_config(make_config(rules, fallbacks=["model-a"]))

    def test_error_message_contains_rule_name(self):
        rules = [make_rule("code-generation", ["model-a", "model-a"])]
        with pytest.raises(ValueError, match="code-generation"):
            validate_no_duplicates_in_config(make_config(rules, fallbacks=[]))

    def test_error_message_contains_provider_and_model(self):
        rules = [make_rule("rule-1", ["model-a", "model-a"])]
        with pytest.raises(ValueError, match="anthropic") as exc_info:
            validate_no_duplicates_in_config(make_config(rules, fallbacks=[]))
        assert "claude-3" in str(exc_info.value)

    def test_only_first_failing_rule_is_reported(self):
        rules = [
            make_rule("rule-1", ["model-a", "model-b"]),
            make_rule("rule-2", ["model-c", "model-c"]),
        ]
        with pytest.raises(ValueError, match="rule-2"):
            validate_no_duplicates_in_config(make_config(rules, fallbacks=[]))

    def test_empty_targets_passes(self):
        rules = [make_rule("rule-1", [])]
        validate_no_duplicates_in_config(make_config(rules, fallbacks=["model-a"]))


class TestIsMatchingRule:
    def test_matches_when_name_and_value_match(self):
        rule = RoutingRuleConfig(
            id="1",
            name="code generation rule",
            match=RuleMatchConfig(name="task-type", value="code_generation"),
            targets=[],
        )
        assert is_matching_rule("task-type", "code_generation", rule) is True

    def test_no_match_when_name_differs(self):
        rule = RoutingRuleConfig(
            id="1",
            name="code generation rule",
            match=RuleMatchConfig(name="task-type", value="code_generation"),
            targets=[],
        )
        assert is_matching_rule("wrong-name", "code_generation", rule) is False

    def test_no_match_when_value_differs(self):
        rule = RoutingRuleConfig(
            id="1",
            name="code generation rule",
            match=RuleMatchConfig(name="task-type", value="code_generation"),
            targets=[],
        )
        assert is_matching_rule("task-type", "wrong-value", rule) is False


class TestSelectEntryTarget:
    def test_returns_a_target_alias(self):
        targets = [
            TargetConfig(alias="openai-gpt4", weight=1),
            TargetConfig(alias="anthropic-claude", weight=1),
        ]
        rng = random.Random(42)
        result = select_entry_target(targets, rng=rng)
        assert result in ("openai-gpt4", "anthropic-claude")

    def test_deterministic_with_seeded_rng(self):
        targets = [
            TargetConfig(alias="openai-gpt4", weight=1),
            TargetConfig(alias="anthropic-claude", weight=1),
        ]
        rng1 = random.Random(42)
        rng2 = random.Random(42)
        assert select_entry_target(targets, rng=rng1) == select_entry_target(targets, rng=rng2)

    def test_respects_weights(self):
        targets = [
            TargetConfig(alias="openai-gpt4", weight=100),
            TargetConfig(alias="anthropic-claude", weight=0),
        ]
        rng = random.Random(42)
        result = select_entry_target(targets, rng=rng)
        assert result == "openai-gpt4"


class TestBuildAttemptChain:
    def test_entry_target_is_first(self):
        targets = [
            TargetConfig(alias="openai-gpt4", weight=1),
            TargetConfig(alias="anthropic-claude", weight=1),
            TargetConfig(alias="gemini-pro", weight=1),
        ]
        chain = build_attempt_chain("anthropic-claude", targets)
        assert chain[0] == "anthropic-claude"

    def test_entry_target_not_duplicated(self):
        targets = [
            TargetConfig(alias="openai-gpt4", weight=1),
            TargetConfig(alias="anthropic-claude", weight=1),
        ]
        chain = build_attempt_chain("openai-gpt4", targets)
        assert chain.count("openai-gpt4") == 1

    def test_all_targets_included(self):
        targets = [
            TargetConfig(alias="openai-gpt4", weight=1),
            TargetConfig(alias="anthropic-claude", weight=1),
            TargetConfig(alias="gemini-pro", weight=1),
        ]
        chain = build_attempt_chain("openai-gpt4", targets)
        assert set(chain) == {"openai-gpt4", "anthropic-claude", "gemini-pro"}


class TestSortCostMap:
    def test_sorts_by_input_cost_ascending(self):
        items = [
            TargetCostConfig(
                alias="expensive", input_tokens_cost_per_1M=10.0, output_tokens_cost_per_1M=1.0
            ),
            TargetCostConfig(
                alias="cheap", input_tokens_cost_per_1M=1.0, output_tokens_cost_per_1M=1.0
            ),
            TargetCostConfig(
                alias="mid", input_tokens_cost_per_1M=5.0, output_tokens_cost_per_1M=1.0
            ),
        ]
        result = sort_cost_map(items)
        assert [r.alias for r in result] == ["cheap", "mid", "expensive"]

    def test_tiebreaks_by_output_cost_ascending(self):
        items = [
            TargetCostConfig(
                alias="same-input-high-output",
                input_tokens_cost_per_1M=5.0,
                output_tokens_cost_per_1M=20.0,
            ),
            TargetCostConfig(
                alias="same-input-low-output",
                input_tokens_cost_per_1M=5.0,
                output_tokens_cost_per_1M=5.0,
            ),
        ]
        result = sort_cost_map(items)
        assert [r.alias for r in result] == ["same-input-low-output", "same-input-high-output"]

    def test_mixed_input_and_output_costs(self):
        items = [
            TargetCostConfig(
                alias="a", input_tokens_cost_per_1M=3.0, output_tokens_cost_per_1M=10.0
            ),
            TargetCostConfig(
                alias="b", input_tokens_cost_per_1M=1.0, output_tokens_cost_per_1M=50.0
            ),
            TargetCostConfig(
                alias="c", input_tokens_cost_per_1M=3.0, output_tokens_cost_per_1M=2.0
            ),
        ]
        result = sort_cost_map(items)
        assert [r.alias for r in result] == ["b", "c", "a"]
