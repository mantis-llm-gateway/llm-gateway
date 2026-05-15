import json
import logging
from typing import Protocol

import numpy as np


class Embedder(Protocol):
    """
    Anything that turns text into a vector.
    """

    DIMENSIONS: int

    def embed(self, text: str) -> list[float]: ...


class FakeEmbedder:
    """
    Useful for local testing of the cache.

    Use this (not BedrockEmbedder) for testing semantic cache (storing, TTL, etc.) without Bedrock.

    This is only for creating fake vectors and is not for testing semantic similarity.
    """

    DIMENSIONS: int = 1024

    def embed(self, text: str) -> list[float]:
        # Deterministic: same text → same vector.
        # Hash-based so different texts get different vectors.
        import hashlib

        seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(self.DIMENSIONS).astype(np.float32)
        vec /= np.linalg.norm(vec)  # normalize, like Titan does
        return vec.tolist()


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
        logging.info(f"Embedding (first 5 values): {embedding[:5]}")
        return embedding
