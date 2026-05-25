from collections.abc import AsyncGenerator
from types import TracebackType
from typing import Any, Protocol, TypedDict, cast

import aioboto3  # type: ignore

# we should not import environment variables from .env in production,
# so delete this once it is being used in production.
from dotenv import load_dotenv

load_dotenv()


class _Text(TypedDict):
    text: str


class Message(TypedDict):
    role: str
    content: list[_Text]


class _AsyncClientContext(Protocol):
    async def __aenter__(self) -> Any: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...


class ProviderAdaptor:
    def __init__(self, region_name: str):
        self.session = aioboto3.Session()
        self.region_name = region_name

    def _bedrock_client(self) -> _AsyncClientContext:
        return cast(
            _AsyncClientContext,
            self.session.client("bedrock-runtime", region_name=self.region_name),
        )

    async def send_request(self, model_id: str, messages: list[Message]) -> str:
        async with self._bedrock_client() as client:
            response = await client.converse(modelId=model_id, messages=messages)
            return response["output"]["message"]["content"][0]["text"] or ""

    async def stream_request(
        self, model_id: str, messages: list[Message]
    ) -> AsyncGenerator[str, None]:
        async with self._bedrock_client() as client:
            response = await client.converse_stream(modelId=model_id, messages=messages)

            async for event in response["stream"]:
                if "contentBlockDelta" in event:
                    delta = event["contentBlockDelta"]["delta"]
                    if "text" in delta:
                        yield delta["text"]
