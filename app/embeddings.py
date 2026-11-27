"""Embedding callers. Tests use the fake. The app uses the course gateway."""

import hashlib
import json
import math
import os
import re
import urllib.request
from typing import Protocol

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


class Embedder(Protocol):
    """Turns texts into vectors of EMBEDDING_DIMENSIONS numbers."""

    model: str

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per text, in the same order."""


def content_hash(model: str, source: str, place: str, text: str) -> str:
    """Return the hash of the model, the source, the place, and the text.

    A stored passage is rewritten only when this hash changes.
    """
    return hashlib.sha256(f"{model}\n{source}\n{place}\n{text}".encode()).hexdigest()


class GatewayEmbedder:
    """Sends texts to the course gateway's embeddings endpoint."""

    def __init__(self, model: str = EMBEDDING_MODEL) -> None:
        base_url = os.environ["LLM_API_GATEWAY"].rstrip("/")
        self.url = f"{base_url}/embeddings"
        self.api_key = os.environ["LLM_API_TOKEN"]
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one gateway vector per text."""
        payload = json.dumps({"model": self.model, "input": texts}).encode()
        request = urllib.request.Request(
            self.url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode())
        ordered = sorted(body["data"], key=lambda item: item["index"])
        vectors = [item["embedding"] for item in ordered]
        for vector in vectors:
            if len(vector) != EMBEDDING_DIMENSIONS:
                raise ValueError(
                    f"Expected {EMBEDDING_DIMENSIONS} dimensions, got {len(vector)}."
                )
        return vectors


class FakeEmbedder:
    """Counts words into hashed positions. It compares words, not meaning."""

    def __init__(self, dimensions: int = EMBEDDING_DIMENSIONS, model: str = "fake-embedding") -> None:
        self.dimensions = dimensions
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one hashed vector per text."""
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        counts = [0.0] * self.dimensions
        for word in re.findall(r"\w+", text.lower()):
            counts[int(hashlib.sha256(word.encode()).hexdigest(), 16) % self.dimensions] += 1
        norm = math.sqrt(sum(value * value for value in counts))
        if norm == 0:
            return counts
        return [value / norm for value in counts]
