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

    def search_by_research_ids(
        self,
        research_ids: List[int],
        limit: int = 5,
        exclude_research_ids: set | None = None,
        research_weights: dict[int, float] | None = None,
    ) -> list[models.ScoredPoint]:
        """
        Search for similar research documents based on a list of research IDs.
        
        1. Fetches all embeddings for the given research_ids
        2. Computes centroid of those embeddings
        3. Uses centroid to search for similar documents
        4. Excludes the original research_ids from results
        
        Returns list of ScoredPoint sorted by similarity (highest first).
        Optional research_weights allows weighted centroid calculation per source research_id.
        """
        if not self.is_enabled:
            return []

        if not research_ids:
            return []

        if exclude_research_ids is None:
            exclude_research_ids = set(research_ids)

        client = self._require_client()

        points = client.scroll(
            collection_name=self.collection_name,
            limit=10000,
            with_payload=True,
            with_vectors=True,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="research_id",
                        match=models.MatchAny(any=research_ids),
                    )
                ]
            ),
        )[0]

        if not points:
            logger.warning("No embeddings found for research_ids: %s", research_ids)
            return []

        embeddings = [point.vector for point in points if point.vector]
        if not embeddings:
            logger.warning("No vectors found for research_ids: %s", research_ids)
            return []

        dimensionality = len(embeddings[0])
        weighted_totals = [0.0] * dimensionality
        total_weight = 0.0

        for point in points:
            vector = point.vector
            if not vector or len(vector) != dimensionality:
                continue

            weight = 1.0
            if research_weights:
                payload = point.payload or {}
                research_id = payload.get("research_id")
                if research_id is not None:
                    weight = float(research_weights.get(research_id, 1.0))

            if weight <= 0:
                continue

            total_weight += weight
            for idx in range(dimensionality):
                weighted_totals[idx] += float(vector[idx]) * weight

        if total_weight == 0:
            logger.warning("Total weight is zero for research_ids: %s", research_ids)
            return []

        centroid = [value / total_weight for value in weighted_totals]

        exclude_research_ids_list = list(exclude_research_ids) if exclude_research_ids else []
        search_filter = None
        if exclude_research_ids_list:
            search_filter = models.Filter(
                must_not=[
                    models.FieldCondition(
                        key="research_id",
                        match=models.MatchAny(any=exclude_research_ids_list),
                    )
                ]
            )

        try:
            search_results = client.query_points(
                collection_name=self.collection_name,
                query=centroid,
                query_filter=search_filter,
                limit=limit,
            )
            return search_results.points
        except Exception as e:
            logger.warning("Error searching Qdrant by research_ids: %s", e)
            return []


qdrant_service = QdrantService()