import logging
from uuid import NAMESPACE_URL, uuid5
from typing import List

from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.core.config import settings

logger = logging.getLogger(__name__)


class QdrantService:
    def __init__(self) -> None:
        self.endpoint = settings.QDRANT_ENDPOINT
        self.api_key = settings.QDRANT_API_KEY
        self.collection_name = settings.QDRANT_RESEARCH_COLLECTION
        self.timeout_seconds = settings.QDRANT_TIMEOUT_SECONDS
        self.client: QdrantClient | None = None

        if not self.is_enabled:
            logger.info("Qdrant no configurado; se omitirá la sincronización de embeddings")
            return

        try:
            self.client = QdrantClient(
                url=self.endpoint,
                api_key=self.api_key,
                timeout=self.timeout_seconds,
            )
            logger.info("Qdrant client initialized successfully")
        except Exception as exc:
            logger.warning("Failed to initialize Qdrant client: %s", exc)
            self.client = None

    @property
    def is_enabled(self) -> bool:
        return bool(self.endpoint and self.api_key)

    def _require_client(self) -> QdrantClient:
        if not self.is_enabled:
            raise ValueError("Qdrant configuration is missing")
        if not self.client:
            raise ValueError("Qdrant client could not be initialized")
        return self.client

    def _ensure_collection(self, vector_size: int) -> None:
        client = self._require_client()

        if not client.collection_exists(self.collection_name):
            client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                ),
            )
            logger.info("Created Qdrant collection: %s", self.collection_name)
            return

        collection_info = client.get_collection(self.collection_name)
        collection_size = collection_info.config.params.vectors.size
        if collection_size != vector_size:
            raise ValueError(
                f"Qdrant collection '{self.collection_name}' expects vectors of size {collection_size}, "
                f"but received {vector_size}"
            )

    def upsert_research_embeddings(
        self,
        research_id: int,
        user_id: int,
        title: str,
        research_link: str,
        vector_link: str,
        chunks: List[str],
        embeddings: List[List[float]],
        embedding_model: str | None,
        created_at: str,
    ) -> None:
        if not self.is_enabled:
            logger.info("Skipping Qdrant sync because it is not configured")
            return

        if not embeddings:
            logger.warning("Skipping Qdrant sync for research=%s because no embeddings were generated", research_id)
            return

        if len(chunks) != len(embeddings):
            raise ValueError("Chunk count does not match embedding count")

        vector_size = len(embeddings[0])
        if vector_size == 0:
            raise ValueError("Embeddings must contain at least one dimension")

        self._ensure_collection(vector_size)
        client = self._require_client()

        points: list[models.PointStruct] = []
        for chunk_index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            if len(embedding) != vector_size:
                raise ValueError("All embeddings must have the same dimension")

            points.append(
                models.PointStruct(
                    id=str(uuid5(NAMESPACE_URL, f"research:{research_id}:chunk:{chunk_index}")),
                    vector=embedding,
                    payload={
                        "entity_type": "research",
                        "research_id": research_id,
                        "user_id": user_id,
                        "title": title,
                        "research_link": research_link,
                        "vector_link": vector_link,
                        "embedding_model": embedding_model,
                        "chunk_index": chunk_index,
                        "chunk_text": chunk,
                        "created_at": created_at,
                    },
                )
            )

        client.upsert(
            collection_name=self.collection_name,
            wait=True,
            points=points,
        )
        logger.info(
            "Synced %s research embedding chunks to Qdrant for research=%s",
            len(points),
            research_id,
        )

    def delete_research_embeddings(self, research_id: int) -> None:
        if not self.is_enabled:
            return

        client = self._require_client()
        client.delete(
            collection_name=self.collection_name,
            wait=True,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="research_id",
                            match=models.MatchValue(value=research_id),
                        )
                    ]
                )
            ),
        )
        logger.info("Deleted Qdrant embeddings for research=%s", research_id)


qdrant_service = QdrantService()