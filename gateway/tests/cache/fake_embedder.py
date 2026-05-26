import numpy as np


class FakeEmbedder:
    """
    Useful for local testing of the cache.

    Use this (not BedrockEmbedder) for testing semantic cache (storing, TTL, etc.) without Bedrock.

    This is only for creating fake vectors and is not for testing semantic similarity.
    """

    dimensions: int = 1024

    def embed(self, text: str) -> list[float]:
        # Deterministic: same text → same vector.
        # Hash-based so different texts get different vectors.
        import hashlib

        seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(self.dimensions).astype(np.float32)
        vec /= np.linalg.norm(vec)  # normalize, like Titan does
        return vec.tolist()
