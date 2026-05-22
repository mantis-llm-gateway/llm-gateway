from collections.abc import AsyncGenerator
from typing import TypedDict

import aioboto3  # type: ignore

# we should not import environment variables from .env in production,
# so delete this once it is being used in production.
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
    def __init__(self, region_name: str):
        self.session = aioboto3.Session()
        self.region_name = region_name

    async def send_request(self, model_id: str, messages: list[Message], stream: bool = False):
        if stream:
            async for chunk in self._stream_response(model_id, messages):
                yield chunk
        else:
            yield await self._non_streaming_response(model_id, messages)

    async def _non_streaming_response(
        self, model_id: str, messages: list[Message]
    ) -> TokenChunk | EndOfStream:
        # types in below try block are ignored because aioboto3 doesn't ship type stubs.
        async with self.session.client("bedrock-runtime", region_name=self.region_name) as client:  # type: ignore
            response = await client.converse(  # type: ignore
                modelId=model_id,
                messages=messages,
            )
            return {"token": response["output"]["message"]["content"][0]["text"] or ""}

    async def _stream_response(
        self, model_id: str, messages: list[Message]
    ) -> AsyncGenerator[TokenChunk | EndOfStream, None]:
        # types in below try block are ignored because aioboto3 doesn't ship type stubs.
        async with self.session.client("bedrock-runtime", region_name=self.region_name) as client:  # type: ignore
            response = await client.converse_stream(  # type: ignore
                modelId=model_id,
                messages=messages,
            )
            async for event in response["stream"]:  # type: ignore
                if "contentBlockDelta" in event:
                    delta = event["contentBlockDelta"]["delta"]  # type: ignore
                    if "text" in delta:
                        yield {"token": delta["text"]}
            yield EndOfStream()
