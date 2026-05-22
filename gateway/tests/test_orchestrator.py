import json as _json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.responses import StreamingResponse

from gateway.engine import Abort, CompleteSuccess, Failover, StreamingSuccess
from gateway.orchestrator import orchestrate


async def _gen():
    yield "h"
    yield "i"


@pytest.mark.asyncio
async def test_complete_success_returns_json_with_response(test_context):
    with patch(
        "gateway.orchestrator.execute_attempt",
        new=AsyncMock(return_value=CompleteSuccess(response="hello world")),
    ):
        result = await orchestrate(
            {"task-type": "code_generation"},
            prompt="hi",
            stream=False,
            ctx=test_context,
        )
    assert result is not None
    assert result.status_code == 200
    assert _json.loads(result.body) == {"response": "hello world"}


@pytest.mark.asyncio
async def test_streaming_success_returns_streaming_response(test_context):
    with patch(
        "gateway.orchestrator.execute_attempt",
        new=AsyncMock(return_value=StreamingSuccess(chunks=_gen())),
    ):
        result = await orchestrate(
            {"task-type": "code_generation"},
            prompt="hi",
            stream=True,
            ctx=test_context,
        )
    assert isinstance(result, StreamingResponse)


@pytest.mark.asyncio
async def test_abort_returns_status_and_message(test_context):
    with patch(
        "gateway.orchestrator.execute_attempt",
        new=AsyncMock(return_value=Abort(status_code=401, message="unauthorized")),
    ):
        result = await orchestrate(
            {"task-type": "code_generation"},
            prompt="hi",
            stream=False,
            ctx=test_context,
        )
    assert result is not None
    assert result.status_code == 401


@pytest.mark.asyncio
async def test_failover_exhausts_chain_and_returns_last_status(test_context):
    with patch(
        "gateway.orchestrator.execute_attempt",
        new=AsyncMock(return_value=Failover(status_code=503)),
    ) as mock_attempt:
        result = await orchestrate(
            {"task-type": "code_generation"},
            prompt="hi",
            stream=False,
            ctx=test_context,
        )
    assert mock_attempt.await_count == 2
    assert result is not None
    assert result.status_code == 503


@pytest.mark.asyncio
async def test_cooldown_skips_target(test_context, fake_redis):
    fake_redis._cooldowns.add("cooldown:anthropic:claude-3")
    with patch(
        "gateway.orchestrator.execute_attempt",
        new=AsyncMock(return_value=Failover(status_code=503)),
    ) as mock_attempt:
        await orchestrate(
            {"task-type": "code_generation"},
            prompt="hi",
            stream=False,
            ctx=test_context,
        )
    assert mock_attempt.await_count == 1


@pytest.mark.asyncio
async def test_all_cooled_returns_none(test_context, fake_redis):
    fake_redis._cooldowns.add("cooldown:anthropic:claude-3")
    fake_redis._cooldowns.add("cooldown:openai:gpt-4")
    with patch(
        "gateway.orchestrator.execute_attempt",
        new=AsyncMock(),
    ) as mock_attempt:
        result = await orchestrate(
            {"task-type": "code_generation"},
            prompt="hi",
            stream=False,
            ctx=test_context,
        )
    assert mock_attempt.await_count == 0
    assert result is None
