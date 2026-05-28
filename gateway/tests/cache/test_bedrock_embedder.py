import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from botocore.exceptions import BotoCoreError, ClientError

from gateway.cache.embedders import BedrockEmbedder

EXAMPLE_DIMENSIONS = 1024
EXAMPLE_MODEL_ID = "amazon.titan-embed-text-v2:0"

EMBEDDING = [0.1] * EXAMPLE_DIMENSIONS


def make_mock_bedrock_client(embedder: BedrockEmbedder) -> AsyncMock:
    """Patch the embedder's session so `async with self._bedrock_client()` yields a mock.

    Returns the inner client mock so tests can configure `.invoke_model`.
    """
    client = AsyncMock()
    context_manager = AsyncMock()
    context_manager.__aenter__ = AsyncMock(return_value=client)
    context_manager.__aexit__ = AsyncMock(return_value=False)
    embedder.session.client = MagicMock(return_value=context_manager)
    return client


def make_invoke_model_response(embedding: list[float]) -> dict:
    """Shape that mirrors a real Bedrock `invoke_model` response: a dict with a streaming `body`."""
    body = AsyncMock()
    body.read = AsyncMock(return_value=json.dumps({"embedding": embedding}).encode())
    return {"body": body}


@pytest.fixture
def embedder() -> BedrockEmbedder:
    return BedrockEmbedder(
        region_name="us-east-1",
        embedding_model=EXAMPLE_MODEL_ID,
        dimensions=EXAMPLE_DIMENSIONS,
    )


@pytest.mark.asyncio
async def test_embed_returns_vector_from_response(embedder: BedrockEmbedder):
    client = make_mock_bedrock_client(embedder)
    client.invoke_model = AsyncMock(return_value=make_invoke_model_response(EMBEDDING))

    result = await embedder.embed("hello")

    assert result == EMBEDDING


@pytest.mark.asyncio
async def test_embed_calls_run_concurrently(embedder: BedrockEmbedder):
    """Two embeds fired with gather should overlap, not serialize.

    Each mocked invoke_model sleeps 100ms. Sequentially that's ~200ms total;
    concurrently it should be ~100ms. We assert the concurrent total is well
    under the sequential floor to prove the await actually yields control.
    """
    client = make_mock_bedrock_client(embedder)

    async def slow_invoke(**_kwargs):
        await asyncio.sleep(0.1)
        return make_invoke_model_response(EMBEDDING)

    client.invoke_model = AsyncMock(side_effect=slow_invoke)

    start = time.perf_counter()
    await asyncio.gather(embedder.embed("a"), embedder.embed("b"))
    elapsed = time.perf_counter() - start

    assert elapsed < 0.18, f"calls serialized: {elapsed:.3f}s (expected ~0.1s)"


@pytest.mark.asyncio
async def test_embed_sends_expected_request_to_bedrock(embedder):
    client = make_mock_bedrock_client(embedder)
    client.invoke_model = AsyncMock(return_value=make_invoke_model_response(EMBEDDING))

    await embedder.embed("hello")

    client.invoke_model.assert_awaited_once()
    kwargs = client.invoke_model.await_args.kwargs
    assert kwargs["modelId"] == EXAMPLE_MODEL_ID
    body = json.loads(kwargs["body"])
    assert body == {"inputText": "hello", "dimensions": EXAMPLE_DIMENSIONS, "normalize": True}


@pytest.mark.asyncio
async def test_embed_returns_none_on_client_error(embedder):
    client = make_mock_bedrock_client(embedder)
    client.invoke_model = AsyncMock(
        side_effect=ClientError(
            error_response={"Error": {"Code": "ThrottlingException", "Message": "slow down"}},
            operation_name="InvokeModel",
        )
    )
    result = await embedder.embed("hello")
    assert result is None


@pytest.mark.asyncio
async def test_embed_returns_none_on_botocore_error(embedder):
    client = make_mock_bedrock_client(embedder)
    client.invoke_model = AsyncMock(side_effect=BotoCoreError())
    result = await embedder.embed("hello")
    assert result is None
