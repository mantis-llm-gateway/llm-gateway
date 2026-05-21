from gateway.models import RoutingRuleConfig, RuleMatchConfig
from gateway.routing.rules import is_matching_rule


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
