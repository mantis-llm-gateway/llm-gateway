from typing import NamedTuple

from gateway.models import AliasConfig


class ResolvedTarget(NamedTuple):
    provider: str
    model: str


def resolve_aliases(
    alias_names: list[str], aliases: dict[str, AliasConfig]
) -> list[ResolvedTarget]:
    return [
        ResolvedTarget(provider=aliases[name].provider, model=aliases[name].model)
        for name in alias_names
    ]
