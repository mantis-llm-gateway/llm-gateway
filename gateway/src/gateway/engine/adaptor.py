import sys
from collections.abc import AsyncIterator
from dataclasses import dataclass
from types import TracebackType
from typing import Any, NotRequired, Protocol, TypedDict, cast

import aioboto3  # type: ignore


class _Text(TypedDict):
    text: str


class Message(TypedDict):
    role: str
    content: list[_Text]


class _InferenceConfig(TypedDict, total=False):
    temperature: float
    maxTokens: int


class _ConverseKwargs(TypedDict):
    modelId: str
    messages: list[Message]
    guardrailConfig: NotRequired[dict]
    inferenceConfig: NotRequired[_InferenceConfig]
    system: NotRequired[list[_Text]]


class _AsyncClientContext(Protocol):
    async def __aenter__(self) -> Any: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...


@dataclass(frozen=True)
class GuardrailIntervention:
    response: str
    trace: dict


class StreamResult:
    def __init__(self) -> None:
        self._exhausted = False
        self._guardrail_info: dict = {}
        self._usage_info: dict = {}
        self._chunks: AsyncIterator[str] | None = None

    def __aiter__(self) -> AsyncIterator[str]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[str]:
        assert self._chunks is not None
        async for token in self._chunks:
            yield token
        self._exhausted = True

    @property
    def guardrail_info(self) -> dict:
        if not self._exhausted:
            raise RuntimeError("stream not yet exhausted")
        return self._guardrail_info

    @property
    def usage_info(self) -> dict:
        if not self._exhausted:
            raise RuntimeError("stream not yet exhausted")
        return self._usage_info


class ProviderAdaptor:
    def __init__(
        self,
        region_name: str,
        guardrail_id: str | None,
        guardrail_version: str | None,
    ):
        self.session = aioboto3.Session()
        self.region_name = region_name
        self.guardrail_id = guardrail_id
        self.guardrail_version = guardrail_version

    def _bedrock_client(self) -> _AsyncClientContext:
        return cast(
            _AsyncClientContext,
            self.session.client("bedrock-runtime", region_name=self.region_name),
        )

    def _build_converse_kwargs(
        self,
        model_id: str,
        messages: list[Message],
        *,
        temperature: float | None,
        max_tokens: int | None,
        system: str | None,
        stream: bool,
    ) -> _ConverseKwargs:
        kwargs: _ConverseKwargs = {"modelId": model_id, "messages": messages}

        if self.guardrail_id is not None:
            guardrail_config: dict = {
                "guardrailIdentifier": self.guardrail_id,
                "guardrailVersion": self.guardrail_version,
                "trace": "enabled",
            }

            if stream:
                guardrail_config["streamProcessingMode"] = "sync"

            kwargs["guardrailConfig"] = guardrail_config

        inference_config: _InferenceConfig = {}
        if temperature is not None:
            inference_config["temperature"] = temperature
        if max_tokens is not None:
            inference_config["maxTokens"] = max_tokens
        if inference_config:
            kwargs["inferenceConfig"] = inference_config

        if system is not None:
            kwargs["system"] = [{"text": system}]

        return kwargs

    async def send_request(
        self,
        model_id: str,
        messages: list[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        system: str | None = None,
    ) -> dict | GuardrailIntervention:
        kwargs = self._build_converse_kwargs(
            model_id,
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            system=system,
            stream=False,
        )
        async with self._bedrock_client() as client:
            response = await client.converse(**kwargs)
            if response.get("stopReason") == "guardrail_intervened":
                blocked_text = response["output"]["message"]["content"][0]["text"] or ""
                trace = response.get("trace", {}).get("guardrail", {})
                return GuardrailIntervention(response=blocked_text, trace=trace)

            return {
                "response": response["output"]["message"]["content"][0]["text"] or "",
                "input_tokens": response["usage"]["inputTokens"],
                "output_tokens": response["usage"]["outputTokens"],
            }

    async def stream_request(
        self,
        model_id: str,
        messages: list[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        system: str | None = None,
    ) -> StreamResult:
        kwargs = self._build_converse_kwargs(
            model_id,
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            system=system,
            stream=True,
        )

        client_context = self._bedrock_client()
        client = await client_context.__aenter__()

        try:
            response = await client.converse_stream(**kwargs)
        except BaseException:
            await client_context.__aexit__(*sys.exc_info())
            raise

        result = StreamResult()

        async def chunks() -> AsyncIterator[str]:
            stop_reason = None
            guardrail_trace: dict = {}
            input_tokens = 0
            output_tokens = 0
            try:
                async for event in response["stream"]:
                    if "messageStop" in event:
                        stop_reason = event["messageStop"].get("stopReason")
                    elif "metadata" in event:
                        guardrail_trace = (
                            event.get("metadata", {}).get("trace", {}).get("guardrail", {})
                        )
                        usage = event.get("metadata", {}).get("usage", {})
                        input_tokens = usage.get("inputTokens", 0)
                        output_tokens = usage.get("outputTokens", 0)
                    elif "contentBlockDelta" in event:
                        delta = event["contentBlockDelta"]["delta"]
                        if "text" in delta:
                            yield delta["text"]
            except BaseException:
                await client_context.__aexit__(*sys.exc_info())
                raise
            else:
                if stop_reason == "guardrail_intervened":
                    result._guardrail_info["trace"] = guardrail_trace
                result._usage_info["input_tokens"] = input_tokens
                result._usage_info["output_tokens"] = output_tokens
                await client_context.__aexit__(None, None, None)

        result._chunks = chunks()
        return result
