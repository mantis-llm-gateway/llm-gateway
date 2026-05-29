import json
import logging
from types import TracebackType
from typing import Any, Protocol, cast

import aioboto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)


class _AsyncClientContext(Protocol):
    async def __aenter__(self) -> Any: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...


class Embedder(Protocol):
    """
    Anything that turns text into a vector.
    """

    dimensions: int

    async def embed(self, text: str) -> list[float] | None: ...


class BedrockEmbedder:
    """
    Embeds text using an AWS Bedrock embedding model.

    Returns float vectors. The caller picks the model and output dimensions
    via the constructor.

    Requires AWS credentials discoverable by aioboto3
    and Bedrock access for the configured `embedding_model` in `region_name`.
    """

    def __init__(self, region_name: str, embedding_model: str, dimensions: int):
        self.region_name = region_name
        self.session = aioboto3.Session()
        self._embedding_model = embedding_model
        self.dimensions = dimensions

    def _bedrock_client(self) -> _AsyncClientContext:
        return cast(
            _AsyncClientContext,
            self.session.client("bedrock-runtime", region_name=self.region_name),
        )

    async def embed(self, text: str) -> list[float] | None:
        # Request parameters for Titan V2
        body = json.dumps({"inputText": text, "dimensions": self.dimensions, "normalize": True})

        try:
            async with self._bedrock_client() as client:
                response = await client.invoke_model(
                    body=body,
                    modelId=self._embedding_model,
                    accept="application/json",
                    contentType="application/json",
                )

                response_body = await response["body"].read()

            embedding = json.loads(response_body).get("embedding")

            # TODO: observability logs (see TEA-87)

        except (ClientError, BotoCoreError) as e:
            embedding = None
            logger.warning(
                "bedrock embedding call failed: model=%s error_type=%s error=%s",
                self._embedding_model,
                type(e).__name__,
                e,
            )

        return embedding
