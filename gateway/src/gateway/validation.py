from gateway.models import Config


def validate_config(config: Config) -> None:
    validate_routing_rules_strings(config)
    validate_default_model_existence_in_aliases(config)
    validate_all_target_aliases(config)
    validate_fallback_chain(config)
    validate_no_duplicates_in_config(config)
    validate_uniqueness_of_routing_rule_ids(config)
    validate_weights_in_target_list(config)
    validate_target_retries_val(config)
    validate_initial_response_timeout(config)
    validate_cooldown_ttl(config)
    validate_conversation_size_threshold(config)
    validate_ttl_seconds(config)
    validate_similarity_threshold(config)
    validate_top_k(config)
    validate_conversation_size_threshold(config)


def _validate_non_empty_string(value, field_description: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{field_description} must be a string.")
    if not value:
        raise ValueError(f"{field_description} must not be an empty string.")


def validate_routing_rules_strings(config: Config) -> None:
    for rule in config.routing_rules:
        _validate_non_empty_string(rule.name, f"The rule name of rule with id {rule.id}")
        _validate_non_empty_string(
            rule.match.name, f"The match name field of rule with id {rule.id}"
        )
        _validate_non_empty_string(
            rule.match.value, f"The match value field of rule with id {rule.id}"
        )


def validate_all_target_aliases(config: Config) -> None:
    for rule in config.routing_rules:
        for target in rule.targets:
            if target.alias not in config.aliases:
                raise ValueError(f"{target.alias} is not a valid registered alias.")


def validate_uniqueness_of_routing_rule_ids(config: Config) -> None:
    routing_rules_ids = [rule.id for rule in config.routing_rules]
    if len(routing_rules_ids) != len(set(routing_rules_ids)):
        raise ValueError("Each routing rule must have a unique id.")


def validate_default_model_existence_in_aliases(config: Config) -> None:
    if config.default_model not in config.aliases:
        raise ValueError("The default model is not a configured alias")


def validate_cooldown_ttl(config: Config) -> None:
    if config.cooldown_ttl < 60:
        raise ValueError("The cooldown_ttl field must have a value of 60 or greater.")


def validate_target_retries_val(config: Config) -> None:
    if config.target_retries < 0:
        raise ValueError("The target_retries field must be 0 or greater")


def validate_initial_response_timeout(config: Config) -> None:
    if config.initial_response_timeout < 30:
        raise ValueError("The initial_response_timeout field must be 30 seconds or greater.")


def validate_fallback_chain(config: Config) -> None:
    if len(config.fallbacks) != len(set(config.fallbacks)):
        raise ValueError("The fallback chain must not have duplicates.")

    for fallback in config.fallbacks:
        if fallback not in config.aliases:
            raise ValueError(f"{fallback} is not configured.")


def validate_no_duplicates_in_config(config: Config) -> None:
    for rule in config.routing_rules:
        a_target_list = [target.alias for target in rule.targets]
        a_target_list_with_fallbacks = a_target_list + config.fallbacks
        seen = set()
        for target in a_target_list_with_fallbacks:
            if target in seen:
                msg = (
                    f"Duplicate target found in config for rule '{rule.name}'. "
                    f"Provider: {config.aliases[target].provider}, "
                    f"Model: {config.aliases[target].model}"
                )
                raise ValueError(msg)

            seen.add(target)


def validate_weights_in_target_list(config: Config) -> None:
    for rule in config.routing_rules:
        zeros_count = 0
        total_targets = len(rule.targets)
        for target in rule.targets:
            if target.weight < 0:
                raise ValueError(
                    f"Weight for target {target.alias} for {rule.name} must not be negative"
                )

            if target.weight == 0:
                zeros_count += 1

        if zeros_count == total_targets:
            raise ValueError("All the weights for targets must not be 0")


def validate_temperature_threshold(config: Config) -> None:
    threshold = config.prompt_cache.temperature_threshold
    if not (0.0 <= threshold <= 2.0):
        raise ValueError("The temperature_threshold field must be in [0.0, 2.0].")


def validate_ttl_seconds(config: Config) -> None:
    if config.prompt_cache.ttl_seconds <= 0:
        raise ValueError("The ttl_seconds field must be greater than 0.")


def validate_similarity_threshold(config: Config) -> None:
    if config.prompt_cache.semantic is None:
        return
    threshold = config.prompt_cache.semantic.similarity_threshold
    if not (0.0 <= threshold <= 1.0):
        raise ValueError("The similarity_threshold field must be in [0.0, 1.0].")


def validate_top_k(config: Config) -> None:
    if config.prompt_cache.semantic is None:
        return
    if config.prompt_cache.semantic.top_k <= 0:
        raise ValueError("The top_k field must be greater than 0.")


def validate_conversation_size_threshold(config: Config) -> None:
    if config.prompt_cache.semantic is None:
        return
    if config.prompt_cache.semantic.conversation_size_threshold <= 0:
        raise ValueError("The conversation_size_threshold field must be greater than 0.")
