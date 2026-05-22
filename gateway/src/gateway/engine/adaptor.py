from collections.abc import AsyncGenerator
from typing import TypedDict

import aioboto3  # type: ignore

# we should not import environment variables from .env in production,
# so delete this once it is being used in production.
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()


class TokenChunk(TypedDict):
    token: str


class _Text(TypedDict):
    text: str


class Message(TypedDict):
    role: str
    content: list[_Text]


class EndOfStream:
    pass


class ProviderAdaptor:
    def __init__(self):
        self.session = aioboto3.Session()
        self._client = None
        self._client_context = None

    async def start(self):
        self._client_context = self.session.client("bedrock-runtime", region_name="us-east-1")  # type: ignore
        self._client = await self._client_context.__aenter__()  # type: ignore

    async def shutdown(self):
        if self._client is not None:  # type: ignore
            await self._client_context.__aexit__(None, None, None)  # type: ignore

    async def send_request(self, model_id: str, messages: list[Message], stream: bool = False):
        if stream:
            async for chunk in self._stream_response(model_id, messages):
                yield chunk
        else:
            yield await self._non_streaming_response(model_id, messages)

    async def _non_streaming_response(
        self, model_id: str, messages: list[Message]
    ) -> TokenChunk | EndOfStream:
        try:  # types in below try block are ignored because aioboto3 doesn't ship type stubs.
            response = await self._client.converse(  # type: ignore
                modelId=model_id,
                messages=messages,
            )
            return {"token": response["output"]["message"]["content"][0]["text"] or ""}
        except ClientError:
            raise

    async def _stream_response(
        self, model_id: str, messages: list[Message]
    ) -> AsyncGenerator[TokenChunk | EndOfStream, None]:
        try:  # types in below try block are ignored because aioboto3 doesn't ship type stubs.
            response = await self._client.converse_stream(  # type: ignore
                modelId=model_id,
                messages=messages,
            )
            async for event in response["stream"]:  # type: ignore
                if "contentBlockDelta" in event:
                    delta = event["contentBlockDelta"]["delta"]  # type: ignore
                    if "text" in delta:
                        yield {"token": delta["text"]}
            yield EndOfStream()
        except ClientError:
            raise
