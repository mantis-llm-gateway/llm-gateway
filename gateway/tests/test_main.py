import random
from unittest.mock import patch

import pytest

from gateway.main import (
    AliasConfig,
    RoutingRuleConfig,
    RuleMatchConfig,
    TargetConfig,
    build_attempt_chain,
    check_for_duplicates_in_config,
    is_matching_rule,
    select_entry_target,
)

FAKE_ALIASES = {
    "model-a": AliasConfig(provider="anthropic", model="claude-3", rate_limits={}),
    "model-b": AliasConfig(provider="openai", model="gpt-4", rate_limits={}),
    "model-c": AliasConfig(provider="gemini", model="gemini-pro", rate_limits={}),
}


def make_rule(name: str, aliases: list[str]) -> RoutingRuleConfig:
    return RoutingRuleConfig(
        id="1",
        name=name,
        match=RuleMatchConfig(name="task-type", value="test"),
        targets=[TargetConfig(alias=alias, weight=1) for alias in aliases],
    )


# From Hubert's review for PR 9: Do you also have a test where target A is in cooldown,
# target B is tried and all targets in cooldown return no usable target?
# I guess that should probably wait until you have implemented the cooldown write path though.

# Don't forget to add the test above.


class TestCheckForDuplicatesInConfig:
    def test_no_duplicates_passes(self):
        rules = [make_rule("rule-1", ["model-a", "model-b"])]
        with (
            patch("gateway.main.ROUTING_RULES", rules),
            patch("gateway.main.FALLBACKS", ["model-c"]),
        ):
            check_for_duplicates_in_config()

    def test_duplicate_within_targets_raises(self):
        rules = [make_rule("rule-1", ["model-a", "model-a"])]
        with (
            patch("gateway.main.ROUTING_RULES", rules),
            patch("gateway.main.FALLBACKS", []),
            patch("gateway.main.ALIASES", FAKE_ALIASES),
        ):
            with pytest.raises(ValueError, match="rule-1"):
                check_for_duplicates_in_config()

    def test_duplicate_between_targets_and_fallbacks_raises(self):
        rules = [make_rule("rule-1", ["model-a", "model-b"])]
        with (
            patch("gateway.main.ROUTING_RULES", rules),
            patch("gateway.main.FALLBACKS", ["model-a"]),
            patch("gateway.main.ALIASES", FAKE_ALIASES),
        ):
            with pytest.raises(ValueError, match="rule-1"):
                check_for_duplicates_in_config()

    def test_error_message_contains_rule_name(self):
        rules = [make_rule("code-generation", ["model-a", "model-a"])]
        with (
            patch("gateway.main.ROUTING_RULES", rules),
            patch("gateway.main.FALLBACKS", []),
            patch("gateway.main.ALIASES", FAKE_ALIASES),
        ):
            with pytest.raises(ValueError, match="code-generation"):
                check_for_duplicates_in_config()

    def test_error_message_contains_provider_and_model(self):
        rules = [make_rule("rule-1", ["model-a", "model-a"])]
        with (
            patch("gateway.main.ROUTING_RULES", rules),
            patch("gateway.main.FALLBACKS", []),
            patch("gateway.main.ALIASES", FAKE_ALIASES),
        ):
            with pytest.raises(ValueError, match="anthropic") as exc_info:
                check_for_duplicates_in_config()
            assert "claude-3" in str(exc_info.value)

    def test_only_first_failing_rule_is_reported(self):
        rules = [
            make_rule("rule-1", ["model-a", "model-b"]),
            make_rule("rule-2", ["model-c", "model-c"]),
        ]
        with (
            patch("gateway.main.ROUTING_RULES", rules),
            patch("gateway.main.FALLBACKS", []),
            patch("gateway.main.ALIASES", FAKE_ALIASES),
        ):
            with pytest.raises(ValueError, match="rule-2"):
                check_for_duplicates_in_config()

    def test_empty_targets_passes(self):
        rules = [make_rule("rule-1", [])]
        with (
            patch("gateway.main.ROUTING_RULES", rules),
            patch("gateway.main.FALLBACKS", ["model-a"]),
        ):
            check_for_duplicates_in_config()


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
