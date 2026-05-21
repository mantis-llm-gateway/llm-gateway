import random

from gateway.models import TargetConfig
from gateway.routing.selection import select_entry_target


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
