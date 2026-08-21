"""Embedding provider — OpenAI (primary) with local sentence-transformers fallback."""

from __future__ import annotations

import logging
from typing import Sequence

import numpy as np

from .config import RagConfig

logger = logging.getLogger(__name__)


class Embedder:
    """Embed text chunks into dense vectors.

    Uses OpenAI text-embedding-3-small by default.
    Set --local to use sentence-transformers (free, offline, 384d).
    """

    def __init__(self, config: RagConfig | None = None, *, local: bool = False):
        self.config = config or RagConfig()
        self._local = bool(local)
        self._local_model = None

    @property
    def dim(self) -> int:
        return self.config.embedding_dim

    @property
    def space(self) -> str:
        provider = "sentence-transformers" if self._local else "openai"
        model = (
            self.config.local_embedding_model
            if self._local
            else self.config.embedding_model
        )
        return f"{provider}:{model}:{self.dim}"

    def embed(self, text: str) -> np.ndarray:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)

        if self._local:
            return self._embed_local(texts)
        return self._embed_openai(texts)

    def _embed_openai(self, texts: Sequence[str]) -> np.ndarray:
        from openai import OpenAI

        client = OpenAI()
        texts = [t[:8000] for t in texts]  # OpenAI token limit safety

        resp = client.embeddings.create(
            model=self.config.embedding_model,
            input=list(texts),
            dimensions=self.config.embedding_dim,
        )
        embeddings = [np.array(d.embedding, dtype=np.float32) for d in resp.data]
        return np.stack(embeddings)

    def _embed_local(self, texts: Sequence[str]) -> np.ndarray:
        if self._local_model is None:
            from sentence_transformers import SentenceTransformer

            self._local_model = SentenceTransformer(self.config.local_embedding_model)

        result = np.asarray(
            self._local_model.encode(list(texts), normalize_embeddings=True),
            dtype=np.float32,
        )
        if result.ndim != 2 or result.shape[1] > self.dim:
            raise ValueError(
                "local embedding dimension exceeds configured RAG dimension: "
                f"{result.shape} vs {self.dim}"
            )
        if result.shape[1] < self.dim:
            result = np.pad(result, ((0, 0), (0, self.dim - result.shape[1])))
        return result
