from redis.asyncio import Redis

from gateway.engine.adaptor import ProviderAdaptor
from gateway.engine.verdict import Failover, Verdict
from gateway.routing import ResolvedTarget


async def execute_attempt(
    target: ResolvedTarget,
    *,
    adaptor: ProviderAdaptor,
    redis: Redis,
    target_retries: int,
    cooldown_ttl: int,
) -> Verdict:
    """Run one target with up to `target_retries` retries.

    Returns a typed verdict that the orchestrator translates into HTTP behavior.

    Contract (to be implemented when provider wiring lands):
      - Successful stream completion → Success()
      - 4xx non-429 before stream start → Abort(status_code=e.status_code)
      - 429 → set cooldown key, return Failover(status_code=429)
      - 5xx → retry up to max_attempts; if exhausted, Failover(status_code=last_5xx)

    The loop body that increments `attempts` lives on the 5xx branch; every other
    branch returns. This shape fixes the original CPU spin-wait bug.
    """
    max_attempts = 1 + target_retries
    last_status: int | None = None
    attempts = 0
    while attempts < max_attempts:
        # TODO: build RequestInformation from target + prompt, call
        # adaptor.send_request(...), iterate chunks, translate to Verdict per
        # the contract above. The 429 branch writes:
        #   key = f"cooldown:{target.provider}:{target.model}"
        #   await redis.set(key, 1, ex=cooldown_ttl)
        return Failover(status_code=501, message="executor not yet wired to provider")

    return Failover(status_code=last_status or 500)
