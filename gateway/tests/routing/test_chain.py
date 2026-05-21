from gateway.models import TargetConfig
from gateway.routing.chain import build_attempt_chain


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
