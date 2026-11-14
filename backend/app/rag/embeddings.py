import logging
import math
from threading import Lock
from functools import lru_cache
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingUnavailableError(RuntimeError):
    pass


class SentenceTransformerEmbeddings:
    def __init__(self, model_name: str, device: str = "cpu") -> None:
        self.model_name = model_name
        self.device = device
        self._model: Any | None = None
        self._model_lock = Lock()

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        with self._model_lock:
            if self._model is not None:
                return self._model
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(
                    self.model_name,
                    device=self.device,
                    local_files_only=True,
                )
            except Exception as exc:
                logger.warning(
                    "Local embedding model unavailable (%s)", type(exc).__name__
                )
                raise EmbeddingUnavailableError(
                    "The configured local embedding model is unavailable. "
                    "Install/cache it explicitly; automatic model downloads are disabled."
                ) from exc
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("Embedding query must not be empty.")
        return self._embed([text])[0]

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if not texts or any(not item.strip() for item in texts):
            raise ValueError("Embedding input must contain non-empty text.")
        try:
            vectors = self._load_model().encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except EmbeddingUnavailableError:
            raise
        except Exception as exc:
            raise EmbeddingUnavailableError(
                "Local embedding generation failed."
            ) from exc
        try:
            validated = [[float(value) for value in vector] for vector in vectors]
        except (TypeError, ValueError) as exc:
            raise EmbeddingUnavailableError(
                "Embedding model returned an invalid vector shape."
            ) from exc
        if len(validated) != len(texts):
            raise EmbeddingUnavailableError(
                "Embedding model returned an unexpected batch size."
            )
        dimensions = {len(vector) for vector in validated}
        if len(dimensions) != 1 or not dimensions.pop():
            raise EmbeddingUnavailableError("Embedding model returned invalid dimensions.")
        if any(not math.isfinite(value) for vector in validated for value in vector):
            raise EmbeddingUnavailableError("Embedding model returned non-finite values.")
        return validated


@lru_cache(maxsize=4)
def get_embedding_service(
    model_name: str | None = None,
    device: str | None = None,
) -> SentenceTransformerEmbeddings:
    settings = get_settings()
    return SentenceTransformerEmbeddings(
        model_name or settings.rag_embedding_model,
        device or settings.rag_embedding_device,
    )
