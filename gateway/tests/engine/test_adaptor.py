from collections.abc import AsyncGenerator, Sequence
from types import SimpleNamespace
from typing import TypeGuard
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice

from gateway.engine.adaptor import (
    ConnectionErrorChunk,
    ProviderAdaptor,
    StreamErrorChunk,
    TokenChunk,
)


def is_token_chunk(
    chunk: TokenChunk | StreamErrorChunk | ConnectionErrorChunk,
) -> TypeGuard[TokenChunk]:
    return "token" in chunk


def is_stream_error_chunk(
    chunk: TokenChunk | StreamErrorChunk | ConnectionErrorChunk,
) -> TypeGuard[StreamErrorChunk]:
    return "error" in chunk


def is_any_llm_error_chunk(
    chunk: TokenChunk | StreamErrorChunk | ConnectionErrorChunk,
) -> TypeGuard[ConnectionErrorChunk]:
    return "any_llm_error" in chunk


def make_request(stream: bool = False) -> MagicMock:
    request = MagicMock()
    request.model = "gpt-4o-mini"
    request.prompt = "Hello"
    request.provider = "openai"
    request.stream = stream
    return request


def make_chunk(text: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        id="mock_id", choices=[SimpleNamespace(delta=SimpleNamespace(content=text))]
    )


def make_mock_stream(chunks: Sequence[str | None], error: bool = False) -> MagicMock:

    async def fake_stream(
        mock_chunks: list[SimpleNamespace],
    ) -> AsyncGenerator[SimpleNamespace, None]:
        for chunk in mock_chunks:
            yield chunk

    mock_chunks: list[SimpleNamespace] = []
    for text in chunks:
        chunk = make_chunk(text)
        chunk.choices[0].delta.content = text
        mock_chunks.append(chunk)

    mock_stream = MagicMock()

    mock_stream.__aiter__ = MagicMock(return_value=fake_stream(mock_chunks))
    return mock_stream


@pytest.fixture
def provider_adaptor() -> ProviderAdaptor:
    return ProviderAdaptor()


@pytest.mark.asyncio
async def test_static_response_success(provider_adaptor: ProviderAdaptor):
    mock_response = ChatCompletion(
        id="mock_id",
        model="gpt-4o-mini",
        object="chat.completion",
        created=0,
        choices=[
            Choice(
                index=0,
                message=ChatCompletionMessage(role="assistant", content="Hello"),
                finish_reason="stop",
            )
        ],
    )
    mock_conn = MagicMock()
    mock_conn.acompletion = AsyncMock(return_value=mock_response)
    with patch.object(provider_adaptor, "_get_client", return_value=mock_conn):
        provider_adaptor.provider_connections["openai"] = mock_conn
        results = [r async for r in provider_adaptor.send_request(make_request())]
        assert results == [{"token": "Hello"}]


@pytest.mark.asyncio
async def test_stream_response_success(provider_adaptor: ProviderAdaptor):
    chunks = ["Hel", "lo", " ", "wo", "rld"]
    mock_stream = make_mock_stream(chunks)
    mock_conn = MagicMock()
    mock_conn.acompletion = AsyncMock(return_value=mock_stream)
    with patch.object(provider_adaptor, "_get_client", return_value=mock_conn):
        provider_adaptor.provider_connections["openai"] = mock_conn
        complete_streamed_string = ""
        async for chunk in provider_adaptor.send_request(make_request(stream=True)):
            if chunk == {"token": "END"}:
                break
            if is_token_chunk(chunk):
                complete_streamed_string += chunk["token"]
        assert complete_streamed_string == "Hello world"


@pytest.mark.asyncio
async def test_get_client_only_creates_connection_once(provider_adaptor: ProviderAdaptor):
    with patch("gateway.engine.adaptor.AnyLLM.create") as mock_create:
        provider_adaptor._get_client("openai")  # type: ignore
        provider_adaptor._get_client("openai")  # type: ignore
        assert mock_create.call_count == 1


@pytest.mark.asyncio
async def test_send_request_get_client_error(provider_adaptor: ProviderAdaptor):
    with patch.object(provider_adaptor, "_get_client", side_effect=Exception("connection failed")):
        chunk = await anext(provider_adaptor.send_request(make_request()))
        if is_any_llm_error_chunk(chunk):
            assert str(chunk["any_llm_error"]) == "connection failed"


@pytest.mark.asyncio
async def test_stream_none_content_falls_back_to_empty_string(provider_adaptor: ProviderAdaptor):
    mock_stream = make_mock_stream([None])
    mock_conn = MagicMock()
    mock_conn.acompletion = AsyncMock(return_value=mock_stream)
    with patch.object(provider_adaptor, "_get_client", return_value=mock_conn):
        mock_conn = MagicMock()
        mock_conn.acompletion = AsyncMock(return_value=mock_stream)
        provider_adaptor.provider_connections["openai"] = mock_conn
        results = [r async for r in provider_adaptor.send_request(make_request(stream=True))]
        data_chunks = [r for r in results if r != {"token": "END"}]
        chunk = data_chunks[0]
        if is_token_chunk(chunk):
            assert chunk["token"] == ""
