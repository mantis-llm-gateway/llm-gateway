from collections.abc import AsyncIterator
from typing import TypedDict
from unittest.mock import AsyncMock, MagicMock

import pytest
from botocore.exceptions import ClientError

from gateway.engine import EndOfStream, Message, ProviderAdaptor

MODEL_ID = "google.gemma-3-4b-it"
MESSAGES: list[Message] = [{"role": "user", "content": [{"text": "Hello"}]}]
# list[dict[str, Sequence[Collection[str]]]]


class _TextBlock(TypedDict):
    text: str


class _NonStreamMessage(TypedDict):
    content: list[_TextBlock]


class _NonStreamOutput(TypedDict):
    message: _NonStreamMessage


class NonStreamResponse(TypedDict):
    output: _NonStreamOutput


class _ContentBlockDelta(TypedDict):
    delta: _TextBlock


class _ContentBlockDeltaEvent(TypedDict):
    contentBlockDelta: _ContentBlockDelta


class StreamResponse(TypedDict):
    stream: AsyncIterator[_ContentBlockDeltaEvent]


async def _async_events(*events: _ContentBlockDeltaEvent) -> AsyncIterator[_ContentBlockDeltaEvent]:
    for event in events:
        yield event


def make_non_stream_bedrock_response(text: str) -> NonStreamResponse:
    return {"output": {"message": {"content": [{"text": text}]}}}


def make_stream_bedrock_response(text: str) -> StreamResponse:
    event: _ContentBlockDeltaEvent = {"contentBlockDelta": {"delta": {"text": text}}}
    return {"stream": _async_events(event)}


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
    return ProviderAdaptor(region_name="us-east-1")


@pytest.mark.asyncio
async def test_non_stream_response_success(provider_adaptor: ProviderAdaptor):
    client = make_mock_bedrock_client(provider_adaptor)
    client.converse = AsyncMock(return_value=make_non_stream_bedrock_response("mock response"))
    results = [r async for r in provider_adaptor.send_request(MODEL_ID, MESSAGES)]
    assert results == [{"token": "mock response"}]


@pytest.mark.asyncio
async def test_non_stream_client_error_propagates(provider_adaptor: ProviderAdaptor):
    client = make_mock_bedrock_client(provider_adaptor)
    client.converse = AsyncMock(side_effect=make_client_error())
    with pytest.raises(ClientError):
        async for _ in provider_adaptor.send_request(MODEL_ID, MESSAGES):
            pass


@pytest.mark.asyncio
async def test_stream_response_success(provider_adaptor: ProviderAdaptor):
    client = make_mock_bedrock_client(provider_adaptor)
    client.converse_stream = AsyncMock(return_value=make_stream_bedrock_response("mock response"))
    results = [
        r
        async for r in provider_adaptor.send_request(MODEL_ID, MESSAGES, stream=True)
        if not isinstance(r, EndOfStream)
    ]
    assert results == [{"token": "mock response"}]


@pytest.mark.asyncio
async def test_stream_client_error_propagates(provider_adaptor: ProviderAdaptor):
    client = make_mock_bedrock_client(provider_adaptor)
    client.converse_stream = AsyncMock(side_effect=make_client_error())
    with pytest.raises(ClientError):
        async for _ in provider_adaptor.send_request(MODEL_ID, MESSAGES, stream=True):
            pass
