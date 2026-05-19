import json
import logging
from typing import Protocol


class Embedder(Protocol):
    """
    Anything that turns text into a vector.
    """

    DIMENSIONS: int

    def embed(self, text: str) -> list[float]: ...


class BedrockEmbedder:
    """
    Embeds text using AWS Bedrock's Titan Text Embeddings V2 model.

    Returns normalized 1024-dim float vectors.
    Requires AWS credentials configured for the bedrock_client passed in,
    plus model access granted for amazon.titan-embed-text-v2:0 in the client's region.
    """

    EMBEDDING_MODEL = "amazon.titan-embed-text-v2:0"
    DIMENSIONS: int = 1024

    def __init__(self, bedrock_client):
        self._bedrock_client = bedrock_client

    def embed(self, text: str) -> list[float]:
        # Request parameters for Titan V2
        body = json.dumps({"inputText": text, "dimensions": self.DIMENSIONS, "normalize": True})

        logging.info("Attempt to get embedding...")
        response = self._bedrock_client.invoke_model(
            body=body,
            modelId=self.EMBEDDING_MODEL,
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
