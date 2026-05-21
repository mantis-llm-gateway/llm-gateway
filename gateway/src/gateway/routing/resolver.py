import random

from gateway.models import Config
from gateway.routing.aliases import ResolvedTarget, resolve_aliases
from gateway.routing.chain import build_attempt_chain
from gateway.routing.rules import is_matching_rule
from gateway.routing.selection import select_entry_target


def resolve_attempt_chain(
    metadata: dict[str, str],
    config: Config,
    rng: random.Random | None = None,
) -> list[ResolvedTarget]:
    """Map a request's metadata to an ordered list of (provider, model) targets to try.

    Uses the first metadata entry; finds the first routing rule whose match condition
    is satisfied. If no rule matches, falls back to the default model. Appends
    configured fallbacks to the chain, then resolves all aliases to (provider, model).
    """
    if metadata:
        header_name, header_value = next(iter(metadata.items()))
        for rule in config.routing_rules:
            if is_matching_rule(header_name, header_value, rule):
                entry_target = select_entry_target(rule.targets, rng)
                attempt_chain = build_attempt_chain(entry_target, rule.targets)
                attempt_chain += config.fallbacks
                return resolve_aliases(attempt_chain, config.aliases)

    return resolve_aliases([config.default_model] + config.fallbacks, config.aliases)
