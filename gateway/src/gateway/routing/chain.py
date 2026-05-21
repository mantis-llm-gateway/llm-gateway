from gateway.models import TargetConfig


def build_attempt_chain(
    entry_target: str, targets_for_matching_rule: list[TargetConfig]
) -> list[str]:
    attempt_chain = [entry_target]
    for target in targets_for_matching_rule:
        if target.alias == entry_target:
            continue
        attempt_chain.append(target.alias)
    return attempt_chain
