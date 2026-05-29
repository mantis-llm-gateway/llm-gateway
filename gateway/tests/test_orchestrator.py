import json as _json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.responses import StreamingResponse

from gateway.engine import Abort, CompleteSuccess, Failover, StreamingSuccess
from gateway.models import ChatMessageRequest, SemanticCacheConfig
from gateway.orchestrator import orchestrate


async def _gen():
    yield "h"
    yield "i"


def make_messages(content: str = "hi") -> list[ChatMessageRequest]:
    return [ChatMessageRequest(role="user", content=content)]


@pytest.mark.asyncio
async def test_complete_success_returns_json_with_response(test_context):
    with patch(
        "gateway.orchestrator.execute_attempt",
        new=AsyncMock(return_value=CompleteSuccess(response="hello world")),
    ):
        result = await orchestrate(
            {"task-type": "code_generation"},
            messages=make_messages(),
            stream=False,
            ctx=test_context,
        )
    assert result is not None
    assert result.status_code == 200
    assert _json.loads(result.body) == {"response": "hello world"}


@pytest.mark.asyncio
async def test_cache_key_includes_full_conversation(test_context):
    messages = [
        ChatMessageRequest(role="user", content="hello"),
        ChatMessageRequest(role="assistant", content="hi"),
        ChatMessageRequest(role="user", content="repeat my first message"),
    ]
    test_context.prompt_cache.get = AsyncMock(return_value=None)
    test_context.prompt_cache.set = AsyncMock()

    with patch(
        "gateway.orchestrator.execute_attempt",
        new=AsyncMock(return_value=CompleteSuccess(response="hello")),
    ):
        await orchestrate(
            {"task-type": "code_generation"},
            messages=messages,
            stream=False,
            ctx=test_context,
        )

    expected_prompt = (
        '[{"content":"hello","role":"user"},'
        '{"content":"hi","role":"assistant"},'
        '{"content":"repeat my first message","role":"user"}]'
    )
    assert test_context.prompt_cache.get.await_args.kwargs["prompt"] == expected_prompt
    assert test_context.prompt_cache.set.await_args.kwargs["prompt"] == expected_prompt


@pytest.mark.asyncio
async def test_long_conversation_skips_semantic_cache_only(test_context):
    test_context.config.prompt_cache.semantic = SemanticCacheConfig(
        similarity_threshold=0.8,
        top_k=3,
        conversation_size_threshold=2,
    )
    test_context.prompt_cache.get = AsyncMock(return_value=None)
    test_context.prompt_cache.set = AsyncMock()

    with patch(
        "gateway.orchestrator.execute_attempt",
        new=AsyncMock(return_value=CompleteSuccess(response="hello")),
    ):
        await orchestrate(
            {"task-type": "code_generation"},
            messages=[
                ChatMessageRequest(role="user", content="one"),
                ChatMessageRequest(role="assistant", content="two"),
                ChatMessageRequest(role="user", content="three"),
            ],
            stream=False,
            ctx=test_context,
        )

    assert test_context.prompt_cache.get.await_args.kwargs["use_semantic"] is False
    assert test_context.prompt_cache.set.await_args.kwargs["use_semantic"] is False


@pytest.mark.asyncio
async def test_streaming_success_returns_streaming_response(test_context):
    with patch(
        "gateway.orchestrator.execute_attempt",
        new=AsyncMock(return_value=StreamingSuccess(chunks=_gen())),
    ):
        result = await orchestrate(
            {"task-type": "code_generation"},
            messages=make_messages(),
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
            messages=make_messages(),
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
            messages=make_messages(),
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
            messages=make_messages(),
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
            messages=make_messages(),
            stream=False,
            ctx=test_context,
        )
    assert mock_attempt.await_count == 0
    assert result is None
