import sys
from collections.abc import AsyncIterator
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
    def __init__(self, region_name: str, guardrails_id: str | None, guardrails_version: str | None):
        self.session = aioboto3.Session()
        self.region_name = region_name
        self.guardrails_id = guardrails_id
        self.guardrails_version = guardrails_version

    def _bedrock_client(self) -> _AsyncClientContext:
        return cast(
            _AsyncClientContext,
            self.session.client("bedrock-runtime", region_name=self.region_name),
        )

    async def send_request(self, model_id: str, messages: list[Message]) -> str:
        kwargs: dict = {"modelId": model_id, "messages": messages}
        if self.guardrails_id is not None:
            kwargs["guardrailConfig"] = {
                "guardrailIdentifier": self.guardrails_id,
                "guardrailVersion": self.guardrails_version,
                "trace": "enabled",
            }
        async with self._bedrock_client() as client:
            response = await client.converse(**kwargs)
            return response["output"]["message"]["content"][0]["text"] or ""

    async def stream_request(self, model_id: str, messages: list[Message]) -> AsyncIterator[str]:
        kwargs: dict = {"modelId": model_id, "messages": messages}
        if self.guardrails_id is not None:
            kwargs["guardrailConfig"] = {
                "guardrailIdentifier": self.guardrails_id,
                "guardrailVersion": self.guardrails_version,
                "streamProcessingMode": "sync",
                "trace": "enabled",
            }

        client_context = self._bedrock_client()
        client = await client_context.__aenter__()

        try:
            response = await client.converse_stream(**kwargs)
        except BaseException:
            await client_context.__aexit__(*sys.exc_info())
            raise

        async def chunks() -> AsyncIterator[str]:
            try:
                async for event in response["stream"]:
                    if "contentBlockDelta" in event:
                        delta = event["contentBlockDelta"]["delta"]
                        if "text" in delta:
                            yield delta["text"]
            except BaseException:
                await client_context.__aexit__(*sys.exc_info())
                raise
            else:
                await client_context.__aexit__(None, None, None)

        return chunks()
