import random

from gateway.models import TargetConfig


def select_entry_target(
    weighted_targets: list[TargetConfig], rng: random.Random | None = None
) -> str:
    if rng is None:
        rng = random.Random()
    aliases = [target.alias for target in weighted_targets]
    weights = [target.weight for target in weighted_targets]
    return rng.choices(aliases, weights=weights, k=1)[0]
