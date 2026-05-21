import pytest

from gateway.engine.executor import execute_attempt
from gateway.engine.verdict import Failover
from gateway.routing import ResolvedTarget


class TestExecuteAttemptStub:
    """Behavior of the executor before provider wiring lands.

    Once `execute_attempt` is implemented against `adaptor.send_request`, these
    tests should be replaced with contract tests:
      - successful stream → Success
      - 4xx non-429 → Abort
      - 429 → Failover + cooldown key written
      - 5xx → retry until exhausted, then Failover
    """

    @pytest.mark.asyncio
    async def test_stub_returns_failover_501(self, fake_adaptor, fake_redis):
        target = ResolvedTarget(provider="anthropic", model="claude-3")
        verdict = await execute_attempt(
            target,
            adaptor=fake_adaptor,
            redis=fake_redis,
            target_retries=2,
            cooldown_ttl=60,
        )
        assert isinstance(verdict, Failover)
        assert verdict.status_code == 501

    @pytest.mark.asyncio
    async def test_stub_does_not_set_cooldown(self, fake_adaptor, fake_redis):
        target = ResolvedTarget(provider="anthropic", model="claude-3")
        await execute_attempt(
            target,
            adaptor=fake_adaptor,
            redis=fake_redis,
            target_retries=0,
            cooldown_ttl=60,
        )
        assert not fake_redis._cooldowns
