import json
import logging
from typing import Protocol


class Embedder(Protocol):
    """
    Anything that turns text into a vector.
    """

    dimensions: int

    def embed(self, text: str) -> list[float]: ...


class BedrockEmbedder:
    """
    Embeds text using an AWS Bedrock embedding model.

    Returns float vectors.

    Requires a Bedrock client configured with credentials
    """

    def __init__(self, client, embedding_model: str, dimensions: int):
        self._bedrock_client = client
        self._embedding_model = embedding_model
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        # Request parameters for Titan V2
        body = json.dumps({"inputText": text, "dimensions": self.dimensions, "normalize": True})

        logging.info("Attempt to get embedding...")
        response = self._bedrock_client.invoke_model(
            body=body,
            modelId=self._embedding_model,
            accept="application/json",
            contentType="application/json",
        )

        response_body = json.loads(response.get("body").read())
        embedding = response_body.get("embedding")

        # TODO: add logging for production logs
        # (requires logging config setup at project entry point)
        # logging.info(f"Embedding (first 5 values): {embedding[:5]}")
        print(f"Embedding (first 5 values): {embedding[:5]}")
        return embedding
