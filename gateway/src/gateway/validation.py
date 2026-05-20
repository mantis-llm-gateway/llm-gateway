from gateway.models import Config


def validate_config(config_dict: Config):
    validate_routing_rules_strings(config_dict)
    validate_default_model_existence_in_aliases(config_dict)
    validate_all_target_aliases(config_dict)
    validate_fallback_chain(config_dict)
    validate_no_duplicates_in_config(config_dict)
    validate_uniqueness_of_routing_rule_ids(config_dict)
    validate_weights_in_target_list(config_dict)
    validate_target_retries_val(config_dict)
    validate_initial_response_timeout(config_dict)
    validate_cooldown_ttl(config_dict)
    validate_cost_based_routing(config_dict)


def _validate_non_empty_string(value, field_description: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{field_description} must be a string.")
    if not value:
        raise ValueError(f"{field_description} must not be an empty string.")


def validate_routing_rules_strings(config_dict: Config) -> None:
    for rule in config_dict.routing_rules:
        _validate_non_empty_string(rule.name, f"The rule name of rule with id {rule.id}")
        _validate_non_empty_string(
            rule.match.name, f"The match name field of rule with id {rule.id}"
        )
        _validate_non_empty_string(
            rule.match.value, f"The match value field of rule with id {rule.id}"
        )


def validate_all_target_aliases(config_dict: Config) -> None:
    for rule in config_dict.routing_rules:
        for target in rule.targets:
            if target.alias not in config_dict.aliases:
                raise ValueError(f"{target.alias} is not a valid registered alias.")


def validate_uniqueness_of_routing_rule_ids(config_dict: Config) -> None:
    routing_rules_ids = [rule.id for rule in config_dict.routing_rules]
    if len(routing_rules_ids) != len(set(routing_rules_ids)):
        raise ValueError("Each routing rule must have a unique id.")


def validate_default_model_existence_in_aliases(config_dict: Config) -> None:
    if config_dict.default_model not in config_dict.aliases:
        raise ValueError("The default model is not a configured alias")


def validate_cooldown_ttl(config_dict: Config) -> None:
    if config_dict.cooldown_ttl < 60:
        raise ValueError("The cooldown_ttl field must have a value of 60 or greater.")


def validate_target_retries_val(config_dict: Config) -> None:
    if config_dict.target_retries < 0:
        raise ValueError("The target_retries field must be 0 or greater")


def validate_initial_response_timeout(config_dict: Config) -> None:
    if config_dict.initial_response_timeout < 30:
        raise ValueError("The initial_response_timeout field must be 30 seconds or greater.")


def validate_fallback_chain(config_dict: Config) -> None:
    if len(config_dict.fallbacks) != len(set(config_dict.fallbacks)):
        raise ValueError("The fallback chain must not have duplicates.")

    for fallback in config_dict.fallbacks:
        if fallback not in config_dict.aliases:
            raise ValueError(f"{fallback} is not configured.")


def validate_no_duplicates_in_config(config_dict: Config) -> None:
    for rule in config_dict.routing_rules:
        a_target_list = [target.alias for target in rule.targets]
        a_target_list_with_fallbacks = a_target_list + config_dict.fallbacks
        seen = set()
        for target in a_target_list_with_fallbacks:
            if target in seen:
                msg = (
                    f"Duplicate target found in config for rule '{rule.name}'. "
                    f"Provider: {config_dict.aliases[target].provider}, "
                    f"Model: {config_dict.aliases[target].model}"
                )
                raise ValueError(msg)

            seen.add(target)


def validate_weights_in_target_list(config_dict: Config) -> None:
    for rule in config_dict.routing_rules:
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


def validate_cost_based_routing(config_dict: Config) -> None:
    cost_based_routing = config_dict.cost_based_routing

    for target in cost_based_routing.cost_map:
        if target.alias not in config_dict.aliases:
            raise ValueError(f"{target.alias} not a valid registered alias")

        if target.input_tokens_cost_per_1M < 0:
            raise ValueError("The cost for input_tokens_cost_per_1M must not be less than 0")

        if target.output_tokens_cost_per_1M < 0:
            raise ValueError("The cost for output_tokens_cost_per_1M must not be less than 0")
