from types import SimpleNamespace

import pytest

from gateway.validation import (
    _validate_non_empty_string,
    validate_all_target_aliases,
    validate_cooldown_ttl,
    validate_default_model_existence_in_aliases,
    validate_fallback_chain,
    validate_initial_response_timeout,
    validate_no_duplicates_in_config,
    validate_routing_rules_strings,
    validate_target_retries_val,
    validate_uniqueness_of_routing_rule_ids,
    validate_weights_in_target_list,
)


def make_match(name="task-type", value="code_gen"):
    return SimpleNamespace(name=name, value=value)


def make_target(alias="model-a", weight=1):
    return SimpleNamespace(alias=alias, weight=weight)


def make_rule(id="1", name="rule-1", match=None, targets=None):
    return SimpleNamespace(
        id=id,
        name=name,
        match=match if match is not None else make_match(),
        targets=targets if targets is not None else [make_target()],
    )


def make_config(**overrides):
    defaults = dict(
        aliases={"model-a": SimpleNamespace(provider="anthropic", model="claude-3")},
        routing_rules=[make_rule()],
        default_model="model-a",
        fallbacks=[],
        target_retries=2,
        initial_response_timeout=30,
        cooldown_ttl=60,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestValidateNonEmptyString:
    def test_raises_if_not_a_string(self):
        with pytest.raises(ValueError, match="must be a string"):
            _validate_non_empty_string(123, "field")

    def test_raises_if_empty_string(self):
        with pytest.raises(ValueError, match="must not be an empty string"):
            _validate_non_empty_string("", "field")

    def test_passes_for_valid_string(self):
        _validate_non_empty_string("hello", "field")


class TestValidateRoutingRulesStrings:
    def test_raises_if_rule_name_is_not_a_string(self):
        config = make_config(routing_rules=[make_rule(name=123)])
        with pytest.raises(ValueError, match="must be a string"):
            validate_routing_rules_strings(config)

    def test_raises_if_rule_name_is_empty(self):
        config = make_config(routing_rules=[make_rule(name="")])
        with pytest.raises(ValueError, match="must not be an empty string"):
            validate_routing_rules_strings(config)

    def test_raises_if_match_name_is_not_a_string(self):
        config = make_config(routing_rules=[make_rule(match=make_match(name=123))])
        with pytest.raises(ValueError, match="must be a string"):
            validate_routing_rules_strings(config)

    def test_raises_if_match_name_is_empty(self):
        config = make_config(routing_rules=[make_rule(match=make_match(name=""))])
        with pytest.raises(ValueError, match="must not be an empty string"):
            validate_routing_rules_strings(config)

    def test_raises_if_match_value_is_not_a_string(self):
        config = make_config(routing_rules=[make_rule(match=make_match(value=123))])
        with pytest.raises(ValueError, match="must be a string"):
            validate_routing_rules_strings(config)

    def test_raises_if_match_value_is_empty(self):
        config = make_config(routing_rules=[make_rule(match=make_match(value=""))])
        with pytest.raises(ValueError, match="must not be an empty string"):
            validate_routing_rules_strings(config)

    def test_passes_for_valid_rule(self):
        validate_routing_rules_strings(make_config())


class TestValidateDefaultModelExistenceInAliases:
    def test_raises_if_default_model_not_in_aliases(self):
        config = make_config(default_model="nonexistent")
        with pytest.raises(ValueError, match="not a configured alias"):
            validate_default_model_existence_in_aliases(config)

    def test_passes_if_default_model_in_aliases(self):
        validate_default_model_existence_in_aliases(make_config())


class TestValidateAllTargetAliases:
    def test_raises_if_target_alias_not_in_aliases(self):
        config = make_config(routing_rules=[make_rule(targets=[make_target(alias="nonexistent")])])
        with pytest.raises(ValueError, match="not a valid registered alias"):
            validate_all_target_aliases(config)

    def test_passes_if_all_target_aliases_valid(self):
        validate_all_target_aliases(make_config())


class TestValidateFallbackChain:
    def test_raises_if_duplicate_fallbacks(self):
        config = make_config(
            aliases={"model-a": SimpleNamespace(provider="anthropic", model="claude-3")},
            fallbacks=["model-a", "model-a"],
        )
        with pytest.raises(ValueError, match="must not have duplicates"):
            validate_fallback_chain(config)

    def test_raises_if_fallback_not_in_aliases(self):
        config = make_config(fallbacks=["nonexistent"])
        with pytest.raises(ValueError):
            validate_fallback_chain(config)

    def test_passes_for_valid_fallback_chain(self):
        config = make_config(
            aliases={
                "model-a": SimpleNamespace(provider="anthropic", model="claude-3"),
                "model-b": SimpleNamespace(provider="openai", model="gpt-4"),
            },
            fallbacks=["model-b"],
        )
        validate_fallback_chain(config)

    def test_passes_for_empty_fallback_chain(self):
        validate_fallback_chain(make_config(fallbacks=[]))


class TestValidateNoDuplicatesInConfig:
    def test_raises_if_duplicate_within_targets(self):
        config = make_config(
            aliases={
                "model-a": SimpleNamespace(provider="anthropic", model="claude-3"),
            },
            routing_rules=[make_rule(targets=[make_target("model-a"), make_target("model-a")])],
        )
        with pytest.raises(ValueError, match="Duplicate"):
            validate_no_duplicates_in_config(config)

    def test_raises_if_duplicate_between_targets_and_fallbacks(self):
        config = make_config(
            aliases={
                "model-a": SimpleNamespace(provider="anthropic", model="claude-3"),
                "model-b": SimpleNamespace(provider="openai", model="gpt-4"),
            },
            routing_rules=[make_rule(targets=[make_target("model-a"), make_target("model-b")])],
            fallbacks=["model-a"],
        )
        with pytest.raises(ValueError, match="Duplicate"):
            validate_no_duplicates_in_config(config)

    def test_passes_for_valid_config(self):
        config = make_config(
            aliases={
                "model-a": SimpleNamespace(provider="anthropic", model="claude-3"),
                "model-b": SimpleNamespace(provider="openai", model="gpt-4"),
            },
            routing_rules=[make_rule(targets=[make_target("model-a")])],
            fallbacks=["model-b"],
        )
        validate_no_duplicates_in_config(config)


class TestValidateUniquenessOfRoutingRuleIds:
    def test_raises_if_duplicate_ids(self):
        config = make_config(routing_rules=[make_rule(id="1"), make_rule(id="1")])
        with pytest.raises(ValueError, match="unique id"):
            validate_uniqueness_of_routing_rule_ids(config)

    def test_passes_for_unique_ids(self):
        config = make_config(routing_rules=[make_rule(id="1"), make_rule(id="2")])
        validate_uniqueness_of_routing_rule_ids(config)


class TestValidateWeightsInTargetList:
    def test_raises_if_any_weight_is_negative(self):
        config = make_config(routing_rules=[make_rule(targets=[make_target(weight=-1)])])
        with pytest.raises(ValueError, match="negative"):
            validate_weights_in_target_list(config)

    def test_raises_if_all_weights_are_zero(self):
        config = make_config(
            routing_rules=[
                make_rule(targets=[make_target(weight=0), make_target(alias="model-b", weight=0)])
            ]
        )
        with pytest.raises(ValueError, match="weights"):
            validate_weights_in_target_list(config)

    def test_passes_if_one_target_is_zero_but_not_all(self):
        config = make_config(
            routing_rules=[
                make_rule(targets=[make_target(weight=0), make_target(alias="model-b", weight=1)])
            ]
        )
        validate_weights_in_target_list(config)

    def test_passes_for_valid_weights(self):
        validate_weights_in_target_list(make_config())


class TestValidateTargetRetriesVal:
    def test_raises_if_negative(self):
        config = make_config(target_retries=-1)
        with pytest.raises(ValueError, match="0 or greater"):
            validate_target_retries_val(config)

    def test_passes_for_zero(self):
        validate_target_retries_val(make_config(target_retries=0))

    def test_passes_for_positive(self):
        validate_target_retries_val(make_config(target_retries=3))


class TestValidateInitialResponseTimeout:
    def test_raises_if_less_than_30(self):
        config = make_config(initial_response_timeout=29)
        with pytest.raises(ValueError, match="30 seconds"):
            validate_initial_response_timeout(config)

    def test_passes_for_exactly_30(self):
        validate_initial_response_timeout(make_config(initial_response_timeout=30))

    def test_passes_for_greater_than_30(self):
        validate_initial_response_timeout(make_config(initial_response_timeout=60))


class TestValidateCooldownTtl:
    def test_raises_if_less_than_60(self):
        config = make_config(cooldown_ttl=59)
        with pytest.raises(ValueError, match="60"):
            validate_cooldown_ttl(config)

    def test_passes_for_exactly_60(self):
        validate_cooldown_ttl(make_config(cooldown_ttl=60))

    def test_passes_for_greater_than_60(self):
        validate_cooldown_ttl(make_config(cooldown_ttl=120))
