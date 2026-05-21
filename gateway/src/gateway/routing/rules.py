from gateway.models import RoutingRuleConfig


def is_matching_rule(header_name: str, header_value: str, rule: RoutingRuleConfig) -> bool:
    return header_name == rule.match.name and header_value == rule.match.value
