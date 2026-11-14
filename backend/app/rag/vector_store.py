import logging
from pathlib import Path
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


class VectorStoreUnavailableError(RuntimeError):
    pass


class ChromaVectorStore:
    def __init__(
        self,
        persist_directory: Path,
        collection_name: str,
        *,
        ephemeral: bool = False,
    ) -> None:
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.ephemeral = ephemeral
        self._client: Any | None = None
        self._collection: Any | None = None
        self._collection_lock = Lock()

    def _get_collection(self) -> Any:
        if self._collection is not None:
            return self._collection
        with self._collection_lock:
            if self._collection is not None:
                return self._collection
            try:
                import chromadb
                from chromadb.config import Settings as ChromaSettings

                if self.ephemeral:
                    self._client = chromadb.EphemeralClient(
                        settings=ChromaSettings(anonymized_telemetry=False)
                    )
                else:
                    self.persist_directory.mkdir(parents=True, exist_ok=True)
                    self._client = chromadb.PersistentClient(
                        path=str(self.persist_directory),
                        settings=ChromaSettings(anonymized_telemetry=False),
                    )
                self._collection = self._client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception as exc:
                logger.warning("ChromaDB unavailable (%s)", type(exc).__name__)
                raise VectorStoreUnavailableError(
                    "Persistent ChromaDB could not be opened."
                ) from exc
        return self._collection

    def upsert(self, chunks: list[dict[str, Any]], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("Chunk and embedding counts do not match.")
        try:
            self._get_collection().upsert(
                ids=[item["chunk_id"] for item in chunks],
                documents=[item["content"] for item in chunks],
                metadatas=[item["metadata"] for item in chunks],
                embeddings=embeddings,
            )
        except VectorStoreUnavailableError:
            raise
        except Exception as exc:
            raise VectorStoreUnavailableError("ChromaDB upsert failed.") from exc

    def delete_document(self, document_id: str) -> None:
        try:
            collection = self._get_collection()
            collection.delete(where={"document_id": document_id})
        except VectorStoreUnavailableError:
            raise
        except Exception as exc:
            raise VectorStoreUnavailableError("ChromaDB deletion failed.") from exc

    def delete_chunks(self, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return
        try:
            self._get_collection().delete(ids=chunk_ids)
        except VectorStoreUnavailableError:
            raise
        except Exception as exc:
            raise VectorStoreUnavailableError("ChromaDB chunk cleanup failed.") from exc

    def search(
        self,
        query_embedding: list[float],
        *,
        top_k: int,
        where: dict[str, Any],
    ) -> list[dict[str, Any]]:
        try:
            result = self._get_collection().query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
            documents = result.get("documents", [[]])[0]
            metadatas = result.get("metadatas", [[]])[0]
            distances = result.get("distances", [[]])[0]
            ids = result.get("ids", [[]])[0]
            return [
                {
                    "chunk_id": ids[index],
                    "content": documents[index],
                    "metadata": metadatas[index],
                    "distance": distances[index],
                }
                for index in range(len(ids))
            ]
        except VectorStoreUnavailableError:
            raise
        except Exception as exc:
            raise VectorStoreUnavailableError("ChromaDB search failed.") from exc

    def documents(self, *, project_id: str) -> list[dict[str, Any]]:
        try:
            result = self._get_collection().get(
                where={"project_id": project_id},
                include=["documents", "metadatas"],
            )
            ids = result.get("ids", [])
            docs = result.get("documents", [])
            metas = result.get("metadatas", [])
            return [
                {
                    "chunk_id": ids[index],
                    "content": docs[index],
                    "metadata": metas[index],
                }
                for index in range(len(ids))
            ]
        except VectorStoreUnavailableError:
            raise
        except Exception as exc:
            raise VectorStoreUnavailableError("ChromaDB listing failed.") from exc

    def document_chunks(
        self,
        *,
        project_id: str,
        document_id: str,
    ) -> list[dict[str, Any]]:
        try:
            result = self._get_collection().get(
                where={
                    "$and": [
                        {"project_id": project_id},
                        {"document_id": document_id},
                    ]
                },
                include=["documents", "metadatas"],
            )
            ids = result.get("ids", [])
            docs = result.get("documents", [])
            metas = result.get("metadatas", [])
            return [
                {
                    "chunk_id": ids[index],
                    "content": docs[index],
                    "metadata": metas[index],
                }
                for index in range(len(ids))
            ]
        except VectorStoreUnavailableError:
            raise
        except Exception as exc:
            raise VectorStoreUnavailableError(
                "ChromaDB document lookup failed."
            ) from exc

    def health(self) -> bool:
        return self._get_collection().count() >= 0
