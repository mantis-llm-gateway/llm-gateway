import json as _json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.responses import StreamingResponse

from gateway.engine import Abort, CompleteSuccess, Failover, StreamingSuccess
from gateway.models import ChatMessageRequest, SemanticCacheConfig
from gateway.orchestrator import orchestrate
from tests.conftest import _client_error_gen, _generic_error_gen, _timeout_gen, make_messages


async def _gen():
    yield "h"
    yield "i"


@pytest.mark.asyncio
async def test_complete_success_returns_json_with_response(test_context):
    with patch(
        "gateway.orchestrator.execute_attempt",
        new=AsyncMock(
            return_value=CompleteSuccess(
                response={"response": "hello world", "input_tokens": 0, "output_tokens": 0}
            )
        ),
    ):
        result = await orchestrate(
            {"task-type": "code_generation"},
            messages=make_messages(),
            stream=False,
            ctx=test_context,
            start_time=datetime.now(UTC),
        )
    assert result is not None
    assert result.status_code == 200
    assert _json.loads(result.body) == {"response": "hello world"}


@pytest.mark.asyncio
async def test_cache_key_includes_full_conversation(test_context):
    test_context.prompt_cache.get = AsyncMock(return_value=None)
    test_context.prompt_cache.set = AsyncMock()

    with patch(
        "gateway.orchestrator.execute_attempt",
        new=AsyncMock(
            return_value=CompleteSuccess(
                response={"response": "hello", "input_tokens": 0, "output_tokens": 0}
            )
        ),
    ):
        await orchestrate(
            {"task-type": "code_generation"},
            messages=[
                ChatMessageRequest(role="user", content="hello"),
                ChatMessageRequest(role="assistant", content="hi"),
                ChatMessageRequest(role="user", content="repeat my first message"),
            ],
            stream=False,
            ctx=test_context,
            start_time=datetime.now(UTC),
        )

    get_prompt = test_context.prompt_cache.get.await_args.kwargs["prompt"]
    set_prompt = test_context.prompt_cache.set.await_args.kwargs["prompt"]
    assert "hello" in get_prompt
    assert "repeat my first message" in get_prompt
    assert get_prompt == set_prompt


@pytest.mark.asyncio
async def test_cache_prompt_includes_system_prompt(test_context):
    test_context.prompt_cache.get = AsyncMock(return_value=None)
    test_context.prompt_cache.set = AsyncMock()

    with patch(
        "gateway.orchestrator.execute_attempt",
        new=AsyncMock(
            return_value=CompleteSuccess(
                response={"response": "hello", "input_tokens": 0, "output_tokens": 0}
            )
        ),
    ):
        await orchestrate(
            {"task-type": "code_generation"},
            messages=[ChatMessageRequest(role="user", content="hello")],
            stream=False,
            ctx=test_context,
            system="You are a pirate.",
            start_time=datetime.now(UTC),
        )

    get_prompt = test_context.prompt_cache.get.await_args.kwargs["prompt"]
    set_prompt = test_context.prompt_cache.set.await_args.kwargs["prompt"]
    assert "You are a pirate." in get_prompt
    assert get_prompt == set_prompt


@pytest.mark.asyncio
async def test_high_temperature_skips_cache_get_and_set(test_context):
    test_context.prompt_cache.get = AsyncMock(return_value=None)
    test_context.prompt_cache.set = AsyncMock()

    with patch(
        "gateway.orchestrator.execute_attempt",
        new=AsyncMock(
            return_value=CompleteSuccess(
                response={"response": "hello", "input_tokens": 0, "output_tokens": 0}
            )
        ),
    ):
        await orchestrate(
            {"task-type": "code_generation"},
            messages=make_messages(),
            stream=False,
            ctx=test_context,
            temperature=0.9,
            start_time=datetime.now(UTC),
        )

    assert test_context.prompt_cache.get.await_count == 0
    assert test_context.prompt_cache.set.await_count == 0


@pytest.mark.asyncio
async def test_temperature_at_threshold_still_uses_cache(test_context):
    test_context.prompt_cache.get = AsyncMock(return_value=None)
    test_context.prompt_cache.set = AsyncMock()

    with patch(
        "gateway.orchestrator.execute_attempt",
        new=AsyncMock(
            return_value=CompleteSuccess(
                response={"response": "hello", "input_tokens": 0, "output_tokens": 0}
            )
        ),
    ):
        await orchestrate(
            {"task-type": "code_generation"},
            messages=make_messages(),
            stream=False,
            ctx=test_context,
            temperature=0.3,
            start_time=datetime.now(UTC),
        )

    assert test_context.prompt_cache.get.await_count == 1
    assert test_context.prompt_cache.set.await_count == 1


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
        new=AsyncMock(
            return_value=CompleteSuccess(
                response={"response": "hello", "input_tokens": 0, "output_tokens": 0}
            )
        ),
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
            start_time=datetime.now(UTC),
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
            start_time=datetime.now(UTC),
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
            start_time=datetime.now(UTC),
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
            start_time=datetime.now(UTC),
        )
    assert mock_attempt.await_count == 2
    assert result is not None
    assert result.status_code == 503


@pytest.mark.asyncio
async def test_cooldown_skips_target(test_context, fake_redis):
    fake_redis._cooldowns.add("gateway:cooldown:anthropic:claude-3")
    with patch(
        "gateway.orchestrator.execute_attempt",
        new=AsyncMock(return_value=Failover(status_code=503)),
    ) as mock_attempt:
        await orchestrate(
            {"task-type": "code_generation"},
            messages=make_messages(),
            stream=False,
            ctx=test_context,
            start_time=datetime.now(UTC),
        )
    assert mock_attempt.await_count == 1


@pytest.mark.asyncio
async def test_all_cooled_returns_503(test_context, fake_redis):
    fake_redis._cooldowns.add("gateway:cooldown:anthropic:claude-3")
    fake_redis._cooldowns.add("gateway:cooldown:openai:gpt-4")
    with patch(
        "gateway.orchestrator.execute_attempt",
        new=AsyncMock(),
    ) as mock_attempt:
        result = await orchestrate(
            {"task-type": "code_generation"},
            messages=make_messages(),
            stream=False,
            ctx=test_context,
            start_time=datetime.now(UTC),
        )
    assert mock_attempt.await_count == 0
    assert result.status_code == 503


@pytest.mark.asyncio
async def test_timeout_stream_abort(test_context):
    with (
        patch(
            "gateway.orchestrator.execute_attempt",
            new=AsyncMock(return_value=StreamingSuccess(chunks=_timeout_gen())),  # type: ignore
        ),
    ):
        result = await orchestrate(
            {"task-type": "code_generation"},
            messages=make_messages(),
            stream=True,
            ctx=test_context,
            start_time=datetime.now(UTC),
        )

        assert isinstance(result, StreamingResponse)

        chunks = [chunk async for chunk in result.body_iterator]
        assert chunks == ["\nerror: provider timeout - check logs for more information\n"]


@pytest.mark.asyncio
async def test_client_error_stream_abort(test_context):
    with patch(
        "gateway.orchestrator.execute_attempt",
        new=AsyncMock(return_value=StreamingSuccess(chunks=_client_error_gen())),
    ):
        result = await orchestrate(
            {"task-type": "code_generation"},
            messages=make_messages(),
            stream=True,
            ctx=test_context,
            start_time=datetime.now(UTC),
        )

        assert isinstance(result, StreamingResponse)

        chunks = [chunk async for chunk in result.body_iterator]
        assert chunks == ["\nerror: provider failure - check logs for more information\n"]


@pytest.mark.asyncio
async def test_generic_exception_stream_abort(test_context):
    with patch(
        "gateway.orchestrator.execute_attempt",
        new=AsyncMock(return_value=StreamingSuccess(chunks=_generic_error_gen())),
    ):
        result = await orchestrate(
            {"task-type": "code_generation"},
            messages=make_messages(),
            stream=True,
            ctx=test_context,
            start_time=datetime.now(UTC),
        )

        assert isinstance(result, StreamingResponse)

        chunks = [chunk async for chunk in result.body_iterator]
        assert chunks == ["\nerror: check logs for more information\n"]
