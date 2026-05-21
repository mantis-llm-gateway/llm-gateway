from unittest.mock import AsyncMock, patch

import pytest

from gateway.engine import Abort, Failover, Success
from gateway.orchestrator import orchestrate


@pytest.mark.asyncio
async def test_success_returns_none(test_context):
    with patch(
        "gateway.orchestrator.execute_attempt",
        new=AsyncMock(return_value=Success()),
    ):
        result = await orchestrate({"task-type": "code_generation"}, test_context)
    assert result is None


@pytest.mark.asyncio
async def test_abort_returns_status_and_message(test_context):
    with patch(
        "gateway.orchestrator.execute_attempt",
        new=AsyncMock(return_value=Abort(status_code=401, message="unauthorized")),
    ):
        result = await orchestrate({"task-type": "code_generation"}, test_context)
    assert result is not None
    assert result.status_code == 401


@pytest.mark.asyncio
async def test_failover_exhausts_chain_and_returns_last_status(test_context):
    # test_config has rule target "model-a" and fallback "fallback" — two attempts.
    with patch(
        "gateway.orchestrator.execute_attempt",
        new=AsyncMock(return_value=Failover(status_code=503)),
    ) as mock_attempt:
        result = await orchestrate({"task-type": "code_generation"}, test_context)
    assert mock_attempt.await_count == 2
    assert result is not None
    assert result.status_code == 503


@pytest.mark.asyncio
async def test_cooldown_skips_target(test_context, fake_redis):
    # Cool down the rule's primary target; orchestrator should skip it and try fallback.
    fake_redis._cooldowns.add("cooldown:anthropic:claude-3")
    with patch(
        "gateway.orchestrator.execute_attempt",
        new=AsyncMock(return_value=Failover(status_code=503)),
    ) as mock_attempt:
        await orchestrate({"task-type": "code_generation"}, test_context)
    assert mock_attempt.await_count == 1  # only the fallback was tried


@pytest.mark.asyncio
async def test_all_cooled_returns_none(test_context, fake_redis):
    fake_redis._cooldowns.add("cooldown:anthropic:claude-3")
    fake_redis._cooldowns.add("cooldown:openai:gpt-4")
    with patch(
        "gateway.orchestrator.execute_attempt",
        new=AsyncMock(),
    ) as mock_attempt:
        result = await orchestrate({"task-type": "code_generation"}, test_context)
    assert mock_attempt.await_count == 0
    assert result is None
