import asyncio
from collections.abc import AsyncIterator
from typing import TypedDict
from unittest.mock import AsyncMock, MagicMock

import pytest
from botocore.exceptions import ClientError

from gateway.engine import Message, ProviderAdaptor

MODEL_ID = "google.gemma-3-4b-it"
MESSAGES: list[Message] = [{"role": "user", "content": [{"text": "Hello"}]}]
STREAM_IDLE_TIMEOUT = 1


class _TextBlock(TypedDict):
    text: str


class _NonStreamMessage(TypedDict):
    content: list[_TextBlock]


class _NonStreamOutput(TypedDict):
    message: _NonStreamMessage


class _Usage(TypedDict):
    inputTokens: int
    outputTokens: int


class NonStreamResponse(TypedDict):
    output: _NonStreamOutput
    usage: _Usage


class _ContentBlockDelta(TypedDict):
    delta: _TextBlock


class _ContentBlockDeltaEvent(TypedDict):
    contentBlockDelta: _ContentBlockDelta


class StreamResponse(TypedDict):
    stream: AsyncIterator[_ContentBlockDeltaEvent]


async def _async_events(*events: _ContentBlockDeltaEvent) -> AsyncIterator[_ContentBlockDeltaEvent]:
    for event in events:
        yield event


async def _async_timeout_events(
    *events: _ContentBlockDeltaEvent,
) -> AsyncIterator[_ContentBlockDeltaEvent]:
    for event in events:
        await asyncio.sleep(STREAM_IDLE_TIMEOUT + 1)
        yield event


def make_non_stream_bedrock_response(text: str) -> NonStreamResponse:
    return {
        "output": {"message": {"content": [{"text": text}]}},
        "usage": {"inputTokens": 10, "outputTokens": 20},
    }


def make_stream_bedrock_response(text: str) -> StreamResponse:
    event: _ContentBlockDeltaEvent = {"contentBlockDelta": {"delta": {"text": text}}}
    return {"stream": _async_events(event)}


def make_stream_bedrock_timedout_response(text: str) -> StreamResponse:
    event: _ContentBlockDeltaEvent = {"contentBlockDelta": {"delta": {"text": text}}}
    return {"stream": _async_timeout_events(event)}


def make_client_error() -> ClientError:
    return ClientError({"Error": {"Code": "InternalError", "Message": "mock failure"}}, "Converse")


def make_mock_bedrock_client(provider_adaptor: ProviderAdaptor) -> AsyncMock:
    client = AsyncMock()
    context_manager = AsyncMock()
    context_manager.__aenter__ = AsyncMock(return_value=client)
    context_manager.__aexit__ = AsyncMock(return_value=False)
    provider_adaptor.session.client = MagicMock(return_value=context_manager)
    return client


@pytest.fixture
def provider_adaptor() -> ProviderAdaptor:
    return ProviderAdaptor(region_name="us-east-1", guardrail_id=None, guardrail_version="1")


@pytest.fixture
def provider_adaptor_with_guardrails() -> ProviderAdaptor:
    return ProviderAdaptor(region_name="us-east-1", guardrail_id="gr-abc123", guardrail_version="2")


@pytest.mark.asyncio
async def test_send_request_success(provider_adaptor: ProviderAdaptor):
    client = make_mock_bedrock_client(provider_adaptor)
    client.converse = AsyncMock(return_value=make_non_stream_bedrock_response("mock response"))

    result = await provider_adaptor.send_request(MODEL_ID, MESSAGES)

    assert result == {"response": "mock response", "input_tokens": 10, "output_tokens": 20}


@pytest.mark.asyncio
async def test_send_request_omits_guardrail_config_when_not_set(provider_adaptor: ProviderAdaptor):
    client = make_mock_bedrock_client(provider_adaptor)
    client.converse = AsyncMock(return_value=make_non_stream_bedrock_response("mock response"))

    await provider_adaptor.send_request(MODEL_ID, MESSAGES)

    _, kwargs = client.converse.call_args
    assert "guardrailConfig" not in kwargs


@pytest.mark.asyncio
async def test_send_request_includes_guardrail_config(
    provider_adaptor_with_guardrails: ProviderAdaptor,
):
    client = make_mock_bedrock_client(provider_adaptor_with_guardrails)
    client.converse = AsyncMock(return_value=make_non_stream_bedrock_response("mock response"))

    await provider_adaptor_with_guardrails.send_request(MODEL_ID, MESSAGES)

    _, kwargs = client.converse.call_args
    assert kwargs["guardrailConfig"] == {
        "guardrailIdentifier": "gr-abc123",
        "guardrailVersion": "2",
        "trace": "enabled",
    }


@pytest.mark.asyncio
async def test_send_request_client_error_propagates(provider_adaptor: ProviderAdaptor):
    client = make_mock_bedrock_client(provider_adaptor)
    client.converse = AsyncMock(side_effect=make_client_error())

    with pytest.raises(ClientError):
        await provider_adaptor.send_request(MODEL_ID, MESSAGES)


@pytest.mark.asyncio
async def test_send_request_includes_inference_config_when_set(provider_adaptor: ProviderAdaptor):
    client = make_mock_bedrock_client(provider_adaptor)
    client.converse = AsyncMock(return_value=make_non_stream_bedrock_response("mock response"))

    await provider_adaptor.send_request(MODEL_ID, MESSAGES, temperature=0.5, max_tokens=256)

    _, kwargs = client.converse.call_args
    assert kwargs["inferenceConfig"] == {"temperature": 0.5, "maxTokens": 256}


@pytest.mark.asyncio
async def test_send_request_omits_inference_config_when_unset(provider_adaptor: ProviderAdaptor):
    client = make_mock_bedrock_client(provider_adaptor)
    client.converse = AsyncMock(return_value=make_non_stream_bedrock_response("mock response"))

    await provider_adaptor.send_request(MODEL_ID, MESSAGES)

    _, kwargs = client.converse.call_args
    assert "inferenceConfig" not in kwargs


@pytest.mark.asyncio
async def test_send_request_includes_only_set_inference_fields(provider_adaptor: ProviderAdaptor):
    client = make_mock_bedrock_client(provider_adaptor)
    client.converse = AsyncMock(return_value=make_non_stream_bedrock_response("mock response"))

    await provider_adaptor.send_request(MODEL_ID, MESSAGES, temperature=0.5)

    _, kwargs = client.converse.call_args
    assert kwargs["inferenceConfig"] == {"temperature": 0.5}


@pytest.mark.asyncio
async def test_send_request_includes_zero_temperature(provider_adaptor: ProviderAdaptor):
    client = make_mock_bedrock_client(provider_adaptor)
    client.converse = AsyncMock(return_value=make_non_stream_bedrock_response("mock response"))

    await provider_adaptor.send_request(MODEL_ID, MESSAGES, temperature=0.0)

    _, kwargs = client.converse.call_args
    assert kwargs["inferenceConfig"] == {"temperature": 0.0}


@pytest.mark.asyncio
async def test_send_request_includes_system_when_set(provider_adaptor: ProviderAdaptor):
    client = make_mock_bedrock_client(provider_adaptor)
    client.converse = AsyncMock(return_value=make_non_stream_bedrock_response("mock response"))

    await provider_adaptor.send_request(MODEL_ID, MESSAGES, system="be brief")

    _, kwargs = client.converse.call_args
    assert kwargs["system"] == [{"text": "be brief"}]


@pytest.mark.asyncio
async def test_send_request_omits_system_when_unset(provider_adaptor: ProviderAdaptor):
    client = make_mock_bedrock_client(provider_adaptor)
    client.converse = AsyncMock(return_value=make_non_stream_bedrock_response("mock response"))

    await provider_adaptor.send_request(MODEL_ID, MESSAGES)

    _, kwargs = client.converse.call_args
    assert "system" not in kwargs


@pytest.mark.asyncio
async def test_stream_request_success(provider_adaptor: ProviderAdaptor):
    client = make_mock_bedrock_client(provider_adaptor)
    client.converse_stream = AsyncMock(return_value=make_stream_bedrock_response("mock response"))

    stream = await provider_adaptor.stream_request(MODEL_ID, MESSAGES, STREAM_IDLE_TIMEOUT)
    results = [token async for token in stream]

    assert results == ["mock response"]


@pytest.mark.asyncio
async def test_stream_request_omits_guardrail_config_when_not_set(
    provider_adaptor: ProviderAdaptor,
):
    client = make_mock_bedrock_client(provider_adaptor)
    client.converse_stream = AsyncMock(return_value=make_stream_bedrock_response("mock response"))

    stream = await provider_adaptor.stream_request(MODEL_ID, MESSAGES, STREAM_IDLE_TIMEOUT)
    _ = [token async for token in stream]

    _, kwargs = client.converse_stream.call_args
    assert "guardrailConfig" not in kwargs


@pytest.mark.asyncio
async def test_stream_request_includes_guardrail_config(
    provider_adaptor_with_guardrails: ProviderAdaptor,
):
    client = make_mock_bedrock_client(provider_adaptor_with_guardrails)
    client.converse_stream = AsyncMock(return_value=make_stream_bedrock_response("mock response"))

    stream = await provider_adaptor_with_guardrails.stream_request(
        MODEL_ID, MESSAGES, STREAM_IDLE_TIMEOUT
    )
    _ = [token async for token in stream]

    _, kwargs = client.converse_stream.call_args
    assert kwargs["guardrailConfig"] == {
        "guardrailIdentifier": "gr-abc123",
        "guardrailVersion": "2",
        "streamProcessingMode": "sync",
        "trace": "enabled",
    }


@pytest.mark.asyncio
async def test_stream_request_client_error_propagates(provider_adaptor: ProviderAdaptor):
    client = make_mock_bedrock_client(provider_adaptor)
    client.converse_stream = AsyncMock(side_effect=make_client_error())

    with pytest.raises(ClientError):
        await provider_adaptor.stream_request(MODEL_ID, MESSAGES, STREAM_IDLE_TIMEOUT)


@pytest.mark.asyncio
async def test_stream_request_includes_inference_config_and_system_when_set(
    provider_adaptor: ProviderAdaptor,
):
    client = make_mock_bedrock_client(provider_adaptor)
    client.converse_stream = AsyncMock(return_value=make_stream_bedrock_response("mock response"))

    result = await provider_adaptor.stream_request(
        MODEL_ID, MESSAGES, STREAM_IDLE_TIMEOUT, temperature=0.5, max_tokens=256, system="be brief"
    )
    _ = [token async for token in result]

    _, kwargs = client.converse_stream.call_args
    assert kwargs["inferenceConfig"] == {"temperature": 0.5, "maxTokens": 256}
    assert kwargs["system"] == [{"text": "be brief"}]


@pytest.mark.asyncio
async def test_stream_idle_timeout(provider_adaptor: ProviderAdaptor):
    client = make_mock_bedrock_client(provider_adaptor)
    client.converse_stream = AsyncMock(
        return_value=make_stream_bedrock_timedout_response("mock response")
    )

    with pytest.raises(ClientError):
        _ = [
            token
            async for token in await provider_adaptor.stream_request(
                MODEL_ID, MESSAGES, STREAM_IDLE_TIMEOUT
            )
        ]
