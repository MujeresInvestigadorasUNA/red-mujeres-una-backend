import logging
from uuid import NAMESPACE_URL, uuid5
from typing import List

import numpy as np
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

    def _ensure_indexes(self, client: QdrantClient) -> None:
        """Ensure that payload indexes exist for filtering."""
        try:
            # Create index for research_id (used in scroll/filter queries)
            client.create_payload_index(
                collection_name=self.collection_name,
                field_name="research_id",
                field_schema=models.PayloadSchemaType.INTEGER,
            )
            logger.info("Created or confirmed payload index for 'research_id'")
        except Exception as e:
            logger.warning("Could not create payload index for 'research_id': %s", e)

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
            self._ensure_indexes(client)
            return

        collection_info = client.get_collection(self.collection_name)
        collection_size = collection_info.config.params.vectors.size
        if collection_size != vector_size:
            raise ValueError(
                f"Qdrant collection '{self.collection_name}' expects vectors of size {collection_size}, "
                f"but received {vector_size}"
            )
        
        self._ensure_indexes(client)

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
            raise ValueError("Qdrant configuration is missing; cannot sync research embeddings")

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

    def has_research_embeddings(self, research_id: int) -> bool:
        """Check whether at least one embedding chunk exists for a research_id."""
        client = self._require_client()
        points, _ = client.scroll(
            collection_name=self.collection_name,
            limit=1,
            with_payload=False,
            with_vectors=False,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="research_id",
                        match=models.MatchValue(value=research_id),
                    )
                ]
            ),
        )
        return bool(points)

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

    def scroll_all_research_vectors(self) -> dict[int, list[list[float]]]:
        """
        Fetches all chunk vectors from Qdrant and groups them by research_id.
        Returns {research_id: [vector, ...]} for centroid computation.
        Single network call replaces N individual blob downloads.
        """
        client = self._require_client()
        all_points: list[models.Record] = []
        next_offset = None

        while True:
            batch, next_offset = client.scroll(
                collection_name=self.collection_name,
                limit=1000,
                offset=next_offset,
                with_payload=["research_id"],
                with_vectors=True,
            )
            all_points.extend(batch)
            if next_offset is None:
                break

        vectors_by_research: dict[int, list[list[float]]] = {}
        for point in all_points:
            if not point.vector or not point.payload:
                continue
            rid = point.payload.get("research_id")
            if rid is None:
                continue
            vectors_by_research.setdefault(rid, []).append(point.vector)

        return vectors_by_research

    def get_weighted_centroid(
        self,
        research_ids: List[int],
        research_weights: dict[int, float] | None = None,
    ) -> list[float] | None:
        """
        Fetches chunk vectors for the given research_ids and returns a single
        weighted centroid vector. Computed once and reused across query iterations.
        Returns None when no vectors are found.
        """
        client = self._require_client()

        points, _ = client.scroll(
            collection_name=self.collection_name,
            limit=10000,
            with_payload=["research_id"],
            with_vectors=True,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="research_id",
                        match=models.MatchAny(any=research_ids),
                    )
                ]
            ),
        )

        if not points:
            logger.warning("No embeddings found for research_ids: %s", research_ids)
            return None

        vectors: list[list[float]] = []
        weights: list[float] = []

        for point in points:
            if not point.vector:
                continue
            weight = 1.0
            if research_weights and point.payload:
                rid = point.payload.get("research_id")
                if rid is not None:
                    weight = float(research_weights.get(rid, 1.0))
            if weight <= 0:
                continue
            vectors.append(point.vector)
            weights.append(weight)

        if not vectors:
            logger.warning("No valid vectors for research_ids: %s", research_ids)
            return None

        matrix = np.array(vectors, dtype=np.float32)
        w = np.array(weights, dtype=np.float32)
        centroid = np.average(matrix, axis=0, weights=w)
        return centroid.tolist()

    # Fields we actually use from each recommended chunk — avoids transferring
    # chunk_text (can be large) and other fields we never read.
    _REC_PAYLOAD_FIELDS = ["research_id", "title", "user_id", "research_link", "vector_link"]

    def query_by_vector(
        self,
        vector: list[float],
        limit: int,
        exclude_research_ids: set[int] | None = None,
    ) -> list[models.ScoredPoint]:
        """
        Searches Qdrant with a pre-computed vector. Only fetches the payload
        fields needed for recommendation output — skips chunk_text and others.
        """
        client = self._require_client()

        search_filter = None
        if exclude_research_ids:
            search_filter = models.Filter(
                must_not=[
                    models.FieldCondition(
                        key="research_id",
                        match=models.MatchAny(any=list(exclude_research_ids)),
                    )
                ]
            )

        try:
            results = client.query_points(
                collection_name=self.collection_name,
                query=vector,
                query_filter=search_filter,
                limit=limit,
                with_payload=self._REC_PAYLOAD_FIELDS,
            )
            return results.points
        except Exception as e:
            logger.warning("Error querying Qdrant by vector: %s", e)
            return []

    _RAG_PAYLOAD_FIELDS = ["research_id", "title", "user_id", "chunk_text"]

    def query_by_vector_for_rag(
        self,
        vector: list[float],
        limit: int,
    ) -> list[models.ScoredPoint]:
        client = self._require_client()
        try:
            results = client.query_points(
                collection_name=self.collection_name,
                query=vector,
                limit=limit,
                with_payload=self._RAG_PAYLOAD_FIELDS,
            )
            return results.points
        except Exception as e:
            logger.warning("Error querying Qdrant for RAG: %s", e)
            return []

    def search_by_research_ids(
        self,
        research_ids: List[int],
        limit: int = 5,
        exclude_research_ids: set | None = None,
        research_weights: dict[int, float] | None = None,
    ) -> list[models.ScoredPoint]:
        """Convenience wrapper: computes centroid then queries. Use get_weighted_centroid +
        query_by_vector directly when the centroid will be reused across multiple calls."""
        if not self.is_enabled or not research_ids:
            return []
        if exclude_research_ids is None:
            exclude_research_ids = set(research_ids)
        centroid = self.get_weighted_centroid(research_ids, research_weights)
        if centroid is None:
            return []
        return self.query_by_vector(centroid, limit, exclude_research_ids)


qdrant_service = QdrantService()