import os
from collections.abc import AsyncGenerator
from typing import Protocol, TypedDict

from any_llm import AnyLLM

# we should not import environment variables from .env in production,
# so delete this once it is being used in production.
from dotenv import load_dotenv

load_dotenv()


class RequestInformation(Protocol):
    model: str
    prompt: str
    provider: str
    stream: bool


class TokenChunk(TypedDict):
    token: str


class ConnectionErrorChunk(TypedDict):
    any_llm_error: Exception


class StreamErrorChunk(TypedDict):
    error: dict[str, str | int]


class ProviderAdaptor:
    def __init__(self):
        self.provider_connections: dict[str, AnyLLM] = {}

    def _get_client(self, provider: str) -> AnyLLM:
        # this key will eventually be pulled from API key management
        # modify this once we are set up to send requests to other providers
        api_key = os.environ.get("OPENAI_API_KEY")

        if not self.provider_connections.get(provider):
            self.provider_connections[provider] = AnyLLM.create(provider, api_key=api_key)
        return self.provider_connections[provider]

    async def send_request(
        self, request_information: RequestInformation
    ) -> AsyncGenerator[TokenChunk | ConnectionErrorChunk | StreamErrorChunk, None]:
        model = request_information.model
        prompt = request_information.prompt
        try:
            provider_connection = self._get_client(request_information.provider)
        except Exception as e:
            yield {"any_llm_error": e}
            return

        if request_information.stream:
            async for chunk in self._stream_response(provider_connection, model, prompt):
                yield chunk
        else:
            yield await self._non_streaming_response(provider_connection, model, prompt)

    async def _non_streaming_response(
        self, provider_connection: AnyLLM, model: str, prompt: str
    ) -> TokenChunk:
        response = await provider_connection.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )
        return {"token": response.choices[0].message.content or ""}

    async def _stream_response(
        self, provider_connection: AnyLLM, model: str, prompt: str
    ) -> AsyncGenerator[TokenChunk | StreamErrorChunk, None]:

        response = await provider_connection.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        async for chunk in response:
            token = chunk.choices[0].delta.content or ""
            yield {"token": token}
        yield {"token": "END"}

    def _build_error_payload(self, code: int, error_type: str, message: str) -> StreamErrorChunk:
        return {"error": {"code": code, "type": error_type, "message": message}}
