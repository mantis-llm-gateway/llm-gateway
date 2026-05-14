import random

from gateway.main import build_attempt_chain, is_matching_rule, select_entry_target


class TestIsMatchingRule:
    def test_matches_when_name_and_value_match(self):
        rule = {
            "id": "1",
            "name": "code generation rule",
            "match": {"name": "task-type", "value": "code_generation"},
            "targets": [],
        }
        assert is_matching_rule("task-type", "code_generation", rule) is True

    def test_no_match_when_name_differs(self):
        rule = {
            "id": "1",
            "name": "code generation rule",
            "match": {"name": "task-type", "value": "code_generation"},
            "targets": [],
        }
        assert is_matching_rule("wrong-name", "code_generation", rule) is False

    def test_no_match_when_value_differs(self):
        rule = {
            "id": "1",
            "name": "code generation rule",
            "match": {"name": "task-type", "value": "code_generation"},
            "targets": [],
        }
        assert is_matching_rule("task-type", "wrong-value", rule) is False


class TestSelectEntryTarget:
    def test_returns_a_target_alias(self):
        targets = [
            {"alias": "openai-gpt4", "weight": 1},
            {"alias": "anthropic-claude", "weight": 1},
        ]
        rng = random.Random(42)
        result = select_entry_target(targets, rng=rng)
        assert result in ("openai-gpt4", "anthropic-claude")

    def test_deterministic_with_seeded_rng(self):
        targets = [
            {"alias": "openai-gpt4", "weight": 1},
            {"alias": "anthropic-claude", "weight": 1},
        ]
        rng1 = random.Random(42)
        rng2 = random.Random(42)
        assert select_entry_target(targets, rng=rng1) == select_entry_target(targets, rng=rng2)

    def test_respects_weights(self):
        targets = [
            {"alias": "openai-gpt4", "weight": 100},
            {"alias": "anthropic-claude", "weight": 0},
        ]
        rng = random.Random(42)
        result = select_entry_target(targets, rng=rng)
        assert result == "openai-gpt4"


class TestBuildAttemptChain:
    def test_entry_target_is_first(self):
        targets = [
            {"alias": "openai-gpt4", "weight": 1},
            {"alias": "anthropic-claude", "weight": 1},
            {"alias": "gemini-pro", "weight": 1},
        ]
        chain = build_attempt_chain("anthropic-claude", targets)
        assert chain[0] == "anthropic-claude"

    def test_entry_target_not_duplicated(self):
        targets = [
            {"alias": "openai-gpt4", "weight": 1},
            {"alias": "anthropic-claude", "weight": 1},
        ]
        chain = build_attempt_chain("openai-gpt4", targets)
        assert chain.count("openai-gpt4") == 1

    def test_all_targets_included(self):
        targets = [
            {"alias": "openai-gpt4", "weight": 1},
            {"alias": "anthropic-claude", "weight": 1},
            {"alias": "gemini-pro", "weight": 1},
        ]
        chain = build_attempt_chain("openai-gpt4", targets)
        assert set(chain) == {"openai-gpt4", "anthropic-claude", "gemini-pro"}
