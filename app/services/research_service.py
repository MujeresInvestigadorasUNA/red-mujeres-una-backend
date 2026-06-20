import io
import json
import logging
import math
import re
import threading
import time
import traceback
from datetime import datetime
from typing import List, Any
from urllib.parse import urlparse

from cachetools import TTLCache
from fastapi import UploadFile
import numpy as np
from openai import AzureOpenAI, RateLimitError
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.research import Research
from app.repositories.research_authors_repository import ResearchAuthorsRepository
from app.repositories.research_like_events_repository import ResearchLikeEventsRepository
from app.repositories.research_likes_repository import ResearchLikesRepository
from app.repositories.research_repository import ResearchRepository
from app.repositories.research_visits_repository import ResearchVisitsRepository
from app.repositories.users_repository import UsersRepository
from app.schemas import research
from app.services.blob_storage_service import blob_storage_service
from app.services.qdrant_service import qdrant_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-process TTL caches
#
# _rec_cache  — recommendations per unique (source_ids, weights, exclude, limit)
#               TTL 120 s: fresh enough for UX, auto-invalidates when interactions
#               change because the cache key encodes the actual source IDs.
#
# _map_cache  — embedding map per (dim, top_k, min_score)
#               TTL 300 s: global view; invalidated explicitly on create/delete.
# ---------------------------------------------------------------------------
_rec_cache: TTLCache = TTLCache(maxsize=512, ttl=120)
_rec_lock = threading.RLock()

_map_cache: TTLCache = TTLCache(maxsize=16, ttl=300)
_map_lock = threading.RLock()


class ResearchService:
    @staticmethod
    def list_research(
        db: Session,
        skip: int = 0,
        limit: int = 50,
        viewer_user_id: int | None = None,
    ) -> list[dict]:
        researches = ResearchRepository.list(db, skip=skip, limit=limit)
        return ResearchService._attach_like_info(db, researches, viewer_user_id)

    @staticmethod
    def get_research(
        db: Session,
        research_id: int,
        viewer_user_id: int | None = None,
    ) -> dict:
        research = ResearchRepository.get_by_id(db, research_id)
        return ResearchService._build_research_details(db, research, viewer_user_id)

    @staticmethod
    def get_research_pdf_url(
        db: Session,
        research_id: int,
        user_email: str,
        expires_minutes: int = 30,
    ) -> dict:
        user = UsersRepository.get_by_email(db, user_email)
        if not user:
            raise ValueError("User not found")
        research = ResearchRepository.get_by_id(db, research_id)

        blob_info = ResearchService._extract_blob_info(research.research_link)
        if not blob_info:
            raise ValueError("Invalid research link")

        container_type, blob_name = blob_info
        if container_type != "documents":
            raise ValueError("Research document not found in documents container")

        return blob_storage_service.generate_blob_sas_urls(
            blob_name=blob_name,
            container_type=container_type,
            expires_minutes=expires_minutes,
            content_type="application/pdf",
        )

    @staticmethod
    def get_user_research(
        db: Session,
        user_id: int,
        viewer_user_id: int | None = None,
    ) -> list[dict]:
        researches = ResearchRepository.get_by_user_id(db, user_id)
        return ResearchService._attach_like_info(db, researches, viewer_user_id)

    @staticmethod
    def register_research_visit(db: Session, user_id: int, research_id: int) -> dict:
        try:
            UsersRepository.get_by_id(db, user_id)
            ResearchRepository.get_by_id(db, research_id)

            visit = ResearchVisitsRepository.create_or_refresh(
                db,
                user_id=user_id,
                research_id=research_id,
            )
            db.commit()

            return {
                "success": True,
                "user_id": user_id,
                "research_id": research_id,
                "visited_at": visit.visited_at,
                "removed_old_visits": 0,
            }
        except ValueError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def get_recent_research_visits(db: Session, user_id: int, limit: int = 5) -> list[dict]:
        UsersRepository.get_by_id(db, user_id)
        normalized_limit = max(1, min(limit, 5))
        visits = ResearchVisitsRepository.list_recent_by_user(db, user_id=user_id, limit=normalized_limit)

        response: list[dict] = []
        for visit in visits:
            if not visit.research:
                continue

            response.append(
                {
                    "research_id": visit.research_id,
                    "title": visit.research.title,
                    "user_id": visit.user_id,
                    "research_link": visit.research.research_link,
                    "visited_at": visit.visited_at,
                }
            )

        return response

    @staticmethod
    def like_research(db: Session, user_id: int, research_id: int) -> dict:
        try:
            UsersRepository.get_by_id(db, user_id)
            ResearchRepository.get_by_id(db, research_id)

            like, _ = ResearchLikesRepository.like(db, user_id=user_id, research_id=research_id)
            ResearchLikeEventsRepository.create(db, user_id=user_id, research_id=research_id, action="like")
            db.commit()

            return {
                "success": True,
                "user_id": user_id,
                "research_id": research_id,
                "is_liked": True,
                "liked_at": like.liked_at,
            }
        except ValueError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def unlike_research(db: Session, user_id: int, research_id: int) -> dict:
        try:
            UsersRepository.get_by_id(db, user_id)
            ResearchRepository.get_by_id(db, research_id)

            like, changed = ResearchLikesRepository.unlike(db, user_id=user_id, research_id=research_id)
            if changed:
                ResearchLikeEventsRepository.create(db, user_id=user_id, research_id=research_id, action="unlike")

            db.commit()

            return {
                "success": True,
                "user_id": user_id,
                "research_id": research_id,
                "is_liked": False,
                "liked_at": like.liked_at if like else None,
            }
        except ValueError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def get_recent_research_likes(db: Session, user_id: int, limit: int = 5) -> list[dict]:
        UsersRepository.get_by_id(db, user_id)
        normalized_limit = max(1, min(limit, 5))
        likes = ResearchLikesRepository.list_recent_active_by_user(db, user_id=user_id, limit=normalized_limit)

        response: list[dict] = []
        for like in likes:
            if not like.research:
                continue

            response.append(
                {
                    "research_id": like.research_id,
                    "title": like.research.title,
                    "user_id": like.user_id,
                    "research_link": like.research.research_link,
                    "liked_at": like.liked_at,
                }
            )

        return response

    @staticmethod
    def get_research_like_history(db: Session, user_id: int, skip: int = 0, limit: int = 50) -> list[dict]:
        UsersRepository.get_by_id(db, user_id)
        normalized_skip = max(0, skip)
        normalized_limit = max(1, min(limit, 200))
        events = ResearchLikeEventsRepository.list_by_user(
            db,
            user_id=user_id,
            skip=normalized_skip,
            limit=normalized_limit,
        )

        response: list[dict] = []
        for event in events:
            if not event.research:
                continue

            response.append(
                {
                    "research_id": event.research_id,
                    "title": event.research.title,
                    "user_id": event.user_id,
                    "research_link": event.research.research_link,
                    "action": event.action,
                    "created_at": event.created_at,
                }
            )

        return response

    @staticmethod
    def _attach_like_info(
        db: Session,
        researches: list[Research],
        viewer_user_id: int | None,
    ) -> list[dict]:
        research_ids = [research.id for research in researches]
        like_counts = ResearchLikesRepository.get_active_counts_by_research_ids(db, research_ids)
        visit_counts = ResearchVisitsRepository.get_counts_by_research_ids(db, research_ids)

        liked_set: set[int] = set()
        if viewer_user_id is not None:
            UsersRepository.get_by_id(db, viewer_user_id)
            liked_set = ResearchLikesRepository.list_active_research_ids_by_user(
                db,
                user_id=viewer_user_id,
                research_ids=research_ids,
            )

        response: list[dict] = []
        for research in researches:
            response.append(
                ResearchService._serialize_research(
                    research=research,
                    likes_count=like_counts.get(research.id, 0),
                    visits_count=visit_counts.get(research.id, 0),
                    is_liked=research.id in liked_set if viewer_user_id is not None else None,
                )
            )

        return response

    @staticmethod
    def _build_research_details(
        db: Session,
        research: Research,
        viewer_user_id: int | None,
    ) -> dict:
        likes_count = ResearchLikesRepository.count_active_by_research(db, research.id)
        visits_count = ResearchVisitsRepository.count_by_research(db, research.id)
        is_liked = None
        if viewer_user_id is not None:
            UsersRepository.get_by_id(db, viewer_user_id)
            is_liked = bool(
                ResearchLikesRepository.list_active_research_ids_by_user(
                    db,
                    user_id=viewer_user_id,
                    research_ids=[research.id],
                )
            )

        return ResearchService._serialize_research(
            research=research,
            likes_count=likes_count,
            visits_count=visits_count,
            is_liked=is_liked,
        )

    @staticmethod
    def _safe_get_research_details(
        db: Session,
        research_id: int,
        viewer_user_id: int | None,
    ) -> dict | None:
        try:
            research = ResearchRepository.get_by_id(db, research_id)
        except ValueError:
            return None
        return ResearchService._build_research_details(db, research, viewer_user_id)

    @staticmethod
    def _serialize_research(
        research: Research,
        likes_count: int,
        visits_count: int,
        is_liked: bool | None,
    ) -> dict:
        owner = research.user
        authors = [
            {
                "user_id": owner.id,
                "first_name": owner.first_name,
                "last_name": owner.last_name,
                "email": owner.email,
            }
        ] + [
            {
                "user_id": ra.user.id,
                "first_name": ra.user.first_name,
                "last_name": ra.user.last_name,
                "email": ra.user.email,
            }
            for ra in research.authors
        ]
        return {
            "id": research.id,
            "user_id": research.user_id,
            "title": research.title,
            "description": research.description,
            "research_link": research.research_link,
            "vector_link": research.vector_link,
            "status": research.status,
            "likes_count": likes_count,
            "visits_count": visits_count,
            "is_liked": is_liked,
            "authors": authors,
        }

    @staticmethod
    def _graph_node_from_research_details(details: dict, node_type: str) -> dict:
        return {
            "id": f"r:{details['id']}",
            "label": details.get("title", "Unknown"),
            "type": node_type,
            "research_id": details.get("id"),
            "user_id": details.get("user_id"),
            "research_link": details.get("research_link"),
            "vector_link": details.get("vector_link"),
            "status": details.get("status"),
            "likes_count": details.get("likes_count"),
            "is_liked": details.get("is_liked"),
        }

    @staticmethod
    def _graph_node_from_payload(
        research_id: int | None,
        title: str,
        user_id: int | None,
        research_link: str | None,
        node_type: str,
    ) -> dict:
        node_id = f"r:{research_id}" if research_id is not None else f"r:unknown:{title}"
        return {
            "id": node_id,
            "label": title,
            "type": node_type,
            "research_id": research_id,
            "user_id": user_id,
            "research_link": research_link,
        }

    @staticmethod
    def _sanitize_title(title: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", title.strip())
        safe = safe.strip("_")
        return safe or "research"

    @staticmethod
    def _extract_blob_info(blob_url: str | None) -> tuple[str, str] | None:
        if not blob_url:
            return None

        parsed = urlparse(blob_url)
        path = parsed.path.lstrip("/")
        if not path:
            return None

        parts = path.split("/", 1)
        if len(parts) != 2:
            return None

        container_name, blob_name = parts
        container_map = {
            settings.AZURE_BLOB_CONTAINER_DOCUMENTS: "documents",
            settings.AZURE_BLOB_CONTAINER_IMAGES: "images",
            settings.AZURE_BLOB_CONTAINER_VECTORIZED: "vectorized",
        }
        container_type = container_map.get(container_name)
        if not container_type:
            return None

        return container_type, blob_name

    @staticmethod
    def _extract_pdf_text(pdf_bytes: bytes) -> str:
        """Extract text from PDF with memory optimization. Limits to first 50MB of text."""
        reader = PdfReader(io.BytesIO(pdf_bytes))
        texts = []
        max_text_size = 50 * 1024 * 1024  # 50MB limit
        total_size = 0
        
        for page in reader.pages:
            page_text = page.extract_text() or ""
            total_size += len(page_text)
            if total_size > max_text_size:
                logger.warning(f"PDF text exceeds {max_text_size} bytes, truncating extraction")
                texts.append(page_text[:max_text_size - sum(len(t) for t in texts)])
                break
            texts.append(page_text)
        
        return "\n".join(texts)

    @staticmethod
    def _chunk_text(text: str, max_chars: int = 3000, overlap: int = 200) -> List[str]:
        """Split text into chunks efficiently without loading entire string into memory."""
        if max_chars <= 0:
            max_chars = 3000
        if overlap >= max_chars:
            overlap = 0
        
        if len(text) <= max_chars:
            return [text.strip()] if text.strip() else []
        
        chunks = []
        lines = text.split('\n')
        current_chunk = []
        current_size = 0
        
        for line in lines:
            line_size = len(line) + 1  # +1 for newline
            
            if current_size + line_size > max_chars and current_chunk:
                # Save current chunk
                chunk_text = '\n'.join(current_chunk).strip()
                if chunk_text:
                    chunks.append(chunk_text)
                
                # Start overlap with last portion
                overlap_lines = []
                overlap_size = 0
                for prev_line in reversed(current_chunk):
                    prev_size = len(prev_line) + 1
                    if overlap_size + prev_size <= overlap:
                        overlap_lines.insert(0, prev_line)
                        overlap_size += prev_size
                    else:
                        break
                
                current_chunk = overlap_lines[:-1] if overlap_lines else []
                current_size = overlap_size - line_size if overlap_lines else 0
            
            current_chunk.append(line)
            current_size += line_size
        
        # Add final chunk
        if current_chunk:
            chunk_text = '\n'.join(current_chunk).strip()
            if chunk_text:
                chunks.append(chunk_text)
        
        return chunks if chunks else [text.strip()]

    @staticmethod
    def _get_azure_openai_client() -> AzureOpenAI:
        if not settings.AZURE_OPENAI_ENDPOINT or not settings.AZURE_OPENAI_API_KEY:
            raise ValueError("Azure OpenAI configuration is missing")
        return AzureOpenAI(
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        )

    @staticmethod
    def _generate_embeddings(chunks: List[str]) -> List[List[float]]:
        if not settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT:
            raise ValueError("Azure OpenAI embedding deployment name is missing")

        client = ResearchService._get_azure_openai_client()
        if not chunks:
            return []

        batch_size = max(1, settings.AZURE_OPENAI_EMBEDDING_BATCH_SIZE)
        max_retries = 3
        embeddings: List[List[float]] = []

        for batch_start in range(0, len(chunks), batch_size):
            batch = chunks[batch_start:batch_start + batch_size]
            for attempt in range(max_retries):
                try:
                    response = client.embeddings.create(
                        input=batch,
                        model=settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
                    )
                    embeddings.extend(item.embedding for item in response.data)
                    break
                except RateLimitError:
                    if attempt == max_retries - 1:
                        raise

                    delay_seconds = min(60, 5 * (2 ** attempt))
                    logger.warning(
                        "Azure OpenAI rate limit hit while embedding research chunks %s-%s; retrying in %ss",
                        batch_start + 1,
                        batch_start + len(batch),
                        delay_seconds,
                    )
                    time.sleep(delay_seconds)

        return embeddings

    @staticmethod
    def _centroid_embedding(embeddings: List[List[float]]) -> List[float]:
        if not embeddings:
            return []

        first = embeddings[0]
        if not first:
            return []

        dimensions = len(first)
        totals = [0.0] * dimensions

        valid_count = 0
        for vector in embeddings:
            if len(vector) != dimensions:
                continue
            valid_count += 1
            for idx in range(dimensions):
                totals[idx] += float(vector[idx])

        if valid_count == 0:
            return []

        return [value / valid_count for value in totals]

    @staticmethod
    def _cosine_similarity(vector_a: List[float], vector_b: List[float]) -> float:
        if not vector_a or not vector_b or len(vector_a) != len(vector_b):
            return 0.0

        dot_product = 0.0
        norm_a = 0.0
        norm_b = 0.0

        for idx in range(len(vector_a)):
            value_a = float(vector_a[idx])
            value_b = float(vector_b[idx])
            dot_product += value_a * value_b
            norm_a += value_a * value_a
            norm_b += value_b * value_b

        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0

        return dot_product / (math.sqrt(norm_a) * math.sqrt(norm_b))

    @staticmethod
    def _sync_research_embeddings_to_qdrant(
        research_id: int,
        user_id: int,
        title: str,
        research_link: str,
        vector_link: str,
        chunks: List[str],
        embeddings: List[List[float]],
        created_at: str,
    ) -> None:
        qdrant_service.upsert_research_embeddings(
            research_id=research_id,
            user_id=user_id,
            title=title,
            research_link=research_link,
            vector_link=vector_link,
            chunks=chunks,
            embeddings=embeddings,
            embedding_model=settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
            created_at=created_at,
        )

        # Hard guarantee: do not commit DB creation unless embeddings are queryable in Qdrant.
        if not qdrant_service.has_research_embeddings(research_id):
            raise ValueError(f"Qdrant sync verification failed for research={research_id}")

    @staticmethod
    def get_related_research(
        db: Session,
        research_id: int,
        limit: int = 5,
        viewer_user_id: int | None = None,
    ) -> list[dict]:
        ResearchRepository.get_by_id(db, research_id)
        qdrant_results = ResearchService._get_qdrant_recommendations_from_source_ids(
            source_research_ids={research_id},
            exclude_research_ids={research_id},
            limit=limit,
            log_context=f"related research_id={research_id}",
            source_weights=None,
        )
        ordered_ids = [r["id"] for r in qdrant_results if r.get("id") is not None]
        researches = ResearchRepository.get_by_ids(db, ordered_ids)
        return ResearchService._attach_like_info(db, researches, viewer_user_id=viewer_user_id)

    @staticmethod
    def get_related_research_from_recent_visits(db: Session, user_id: int, limit: int = 5) -> list[dict]:
        UsersRepository.get_by_id(db, user_id)
        recent_visits = ResearchVisitsRepository.list_recent_by_user(db, user_id=user_id, limit=5)
        if not recent_visits:
            return []

        visited_research_ids = set()

        for visit in recent_visits:
            research = visit.research
            if not research:
                continue

            visited_research_ids.add(research.id)

        if not visited_research_ids:
            return []

        return ResearchService._get_qdrant_recommendations_from_source_ids(
            source_research_ids=visited_research_ids,
            exclude_research_ids=visited_research_ids,
            limit=limit,
            log_context=f"visits user_id={user_id}",
            source_weights=None,
        )

    @staticmethod
    def get_related_research_from_recent_interactions(
        db: Session,
        user_id: int,
        limit: int = 5,
        viewer_user_id: int | None = None,
    ) -> list[dict]:
        UsersRepository.get_by_id(db, user_id)

        recent_visits = ResearchVisitsRepository.list_recent_by_user(db, user_id=user_id, limit=5)
        recent_likes = ResearchLikesRepository.list_recent_active_by_user(db, user_id=user_id, limit=5)

        visited_research_ids = set()
        for visit in recent_visits:
            if visit.research:
                visited_research_ids.add(visit.research.id)

        liked_research_ids = set()
        for like in recent_likes:
            if like.research:
                liked_research_ids.add(like.research.id)

        source_research_ids = visited_research_ids | liked_research_ids

        if not source_research_ids:
            return []

        # Weight interaction sources:
        # - visited only: 1.0
        # - liked only: 1.0
        # - visited + liked: 2.0 (extra relevance)
        source_weights: dict[int, float] = {}
        for research_id in visited_research_ids:
            source_weights[research_id] = source_weights.get(research_id, 0.0) + 1.0
        for research_id in liked_research_ids:
            source_weights[research_id] = source_weights.get(research_id, 0.0) + 1.0

        qdrant_results = ResearchService._get_qdrant_recommendations_from_source_ids(
            source_research_ids=source_research_ids,
            exclude_research_ids=source_research_ids,
            limit=limit,
            log_context=f"interactions user_id={user_id}",
            source_weights=source_weights,
        )

        ordered_ids = [r["id"] for r in qdrant_results if r.get("id") is not None]
        researches = ResearchRepository.get_by_ids(db, ordered_ids)

        return ResearchService._attach_like_info(db, researches, viewer_user_id=viewer_user_id)

    @staticmethod
    def get_research_similarity_graph(
        db: Session,
        research_id: int,
        limit: int = 15,
        min_score: float = 0.0,
        viewer_user_id: int | None = None,
    ) -> dict:
        source_research = ResearchRepository.get_by_id(db, research_id)
        source_details = ResearchService._build_research_details(db, source_research, viewer_user_id)
        source_node = ResearchService._graph_node_from_research_details(source_details, node_type="source")

        nodes_by_id: dict[str, dict[str, Any]] = {source_node["id"]: source_node}
        edges: list[dict[str, Any]] = []

        recommendations = ResearchService._get_qdrant_recommendations_from_source_ids(
            source_research_ids={research_id},
            exclude_research_ids={research_id},
            limit=limit,
            log_context=f"graph research_id={research_id}",
            source_weights=None,
        )

        for rec in recommendations:
            score = float(rec.get("similarity_score", 0.0))
            if score < min_score:
                continue

            rec_id = rec.get("id")
            node = None
            if rec_id is not None:
                details = ResearchService._safe_get_research_details(db, rec_id, viewer_user_id)
                if details:
                    node = ResearchService._graph_node_from_research_details(details, node_type="recommended")

            if not node:
                node = ResearchService._graph_node_from_payload(
                    research_id=rec_id,
                    title=rec.get("title", "Unknown"),
                    user_id=rec.get("user_id"),
                    research_link=rec.get("research_link"),
                    node_type="recommended",
                )

            node_id = node["id"]
            if node_id not in nodes_by_id:
                nodes_by_id[node_id] = node

            edges.append(
                {
                    "source": source_node["id"],
                    "target": node_id,
                    "weight": round(score, 6),
                    "relation": "similarity",
                }
            )

        return {
            "meta": {
                "source_research_id": research_id,
                "limit": limit,
                "min_score": min_score,
                "distance": "cosine",
                "embedding_model": settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
            },
            "nodes": list(nodes_by_id.values()),
            "edges": edges,
        }

    @staticmethod
    def get_research_embedding_map(
        db: Session,
        dim: int = 2,
        top_k: int = 0,
        min_score: float = 0.0,
    ) -> dict:
        normalized_dim = 2 if dim not in (2, 3) else dim

        if not qdrant_service.is_enabled:
            return {
                "meta": {"method": "pca", "dim": normalized_dim, "count": 0},
                "points": [],
                "edges": [],
            }

        map_cache_key = (normalized_dim, top_k, min_score)
        with _map_lock:
            cached_map = _map_cache.get(map_cache_key)
        if cached_map is not None:
            return cached_map

        researches = ResearchRepository.list_all(db)
        if not researches:
            return {
                "meta": {"method": "pca", "dim": normalized_dim, "count": 0},
                "points": [],
                "edges": [],
            }

        research_meta: dict[int, dict[str, Any]] = {
            r.id: {
                "id": r.id,
                "title": r.title,
                "description": r.description,
                "user_id": r.user_id,
                "research_link": r.research_link,
            }
            for r in researches
        }

        vectors_by_research = qdrant_service.scroll_all_research_vectors()

        points_meta: list[dict[str, Any]] = []
        centroids: list[list[float]] = []

        for rid, vectors in vectors_by_research.items():
            if rid not in research_meta:
                continue
            centroid = ResearchService._centroid_embedding(vectors)
            if not centroid:
                continue
            points_meta.append(research_meta[rid])
            centroids.append(centroid)

        if not centroids:
            return {
                "meta": {"method": "pca", "dim": normalized_dim, "count": 0},
                "points": [],
                "edges": [],
            }

        centroids_matrix = np.array(centroids, dtype=float)
        projected = ResearchService._pca_project(centroids_matrix, normalized_dim)
        points: list[dict[str, Any]] = []
        for meta, coords in zip(points_meta, projected):
            entry = {"x": float(coords[0]), "y": float(coords[1])}
            if normalized_dim == 3:
                entry["z"] = float(coords[2])
            points.append({**meta, **entry})

        edges: list[dict[str, Any]] = []
        if top_k > 0 and len(centroids_matrix) > 1:
            norms = np.linalg.norm(centroids_matrix, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1.0, norms)
            normalized = centroids_matrix / norms
            sim_matrix = normalized @ normalized.T

            edge_map: dict[tuple[int, int], float] = {}
            for i in range(len(points_meta)):
                row = sim_matrix[i].copy()
                row[i] = -2.0
                top_indices = np.argsort(row)[::-1][:top_k]
                for j in top_indices:
                    score = float(sim_matrix[i, j])
                    if score < min_score:
                        continue
                    pair = (min(i, j), max(i, j))
                    if pair not in edge_map or score > edge_map[pair]:
                        edge_map[pair] = score

            edges = [
                {
                    "source": points_meta[i]["id"],
                    "target": points_meta[j]["id"],
                    "weight": round(score, 6),
                    "relation": "similarity",
                }
                for (i, j), score in edge_map.items()
            ]

        map_result = {
            "meta": {
                "method": "pca",
                "dim": normalized_dim,
                "count": len(points),
                "top_k": top_k,
                "min_score": min_score,
                "embedding_model": settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
            },
            "points": points,
            "edges": edges,
        }
        with _map_lock:
            _map_cache[map_cache_key] = map_result
        return map_result

    @staticmethod
    def _pca_project(matrix: np.ndarray, dim: int) -> np.ndarray:
        if matrix.ndim != 2:
            raise ValueError("Invalid embedding matrix")

        if matrix.shape[0] == 1:
            padded = np.zeros((1, dim), dtype=float)
            padded[0, 0] = 0.0
            return padded

        centered = matrix - np.mean(matrix, axis=0, keepdims=True)
        covariance = np.cov(centered, rowvar=False)
        eigenvalues, eigenvectors = np.linalg.eigh(covariance)
        order = np.argsort(eigenvalues)[::-1]
        components = eigenvectors[:, order[:dim]]
        return centered @ components

    @staticmethod
    def get_user_recommendation_graph(
        db: Session,
        user_id: int,
        limit: int = 15,
        min_score: float = 0.0,
    ) -> dict:
        UsersRepository.get_by_id(db, user_id)

        visits = ResearchService.get_recent_research_visits(db, user_id=user_id, limit=5)
        likes = ResearchService.get_recent_research_likes(db, user_id=user_id, limit=5)

        visited_ids = {visit["research_id"] for visit in visits}
        liked_ids = {like["research_id"] for like in likes}
        source_ids = visited_ids | liked_ids

        user_node = {
            "id": f"u:{user_id}",
            "label": f"User {user_id}",
            "type": "user",
            "user_id": user_id,
        }

        nodes_by_id: dict[str, dict[str, Any]] = {user_node["id"]: user_node}
        edges: list[dict[str, Any]] = []

        interaction_map: dict[int, dict[str, bool]] = {}
        for visit in visits:
            interaction_map.setdefault(visit["research_id"], {})["visit"] = True
        for like in likes:
            interaction_map.setdefault(like["research_id"], {})["like"] = True

        for research_id, flags in interaction_map.items():
            details = ResearchService._safe_get_research_details(db, research_id, viewer_user_id=user_id)
            if details:
                node = ResearchService._graph_node_from_research_details(details, node_type="source")
            else:
                fallback = None
                for entry in visits + likes:
                    if entry["research_id"] == research_id:
                        fallback = entry
                        break
                node = ResearchService._graph_node_from_payload(
                    research_id=research_id,
                    title=fallback["title"] if fallback else "Unknown",
                    user_id=fallback["user_id"] if fallback else None,
                    research_link=fallback["research_link"] if fallback else None,
                    node_type="source",
                )

            nodes_by_id.setdefault(node["id"], node)

            weight = 0
            if flags.get("visit"):
                weight += 1
            if flags.get("like"):
                weight += 2

            edges.append(
                {
                    "source": user_node["id"],
                    "target": node["id"],
                    "weight": float(weight),
                    "relation": "interaction",
                }
            )

        recommendations = []
        if source_ids:
            source_weights: dict[int, float] = {}
            for research_id in visited_ids:
                source_weights[research_id] = source_weights.get(research_id, 0.0) + 1.0
            for research_id in liked_ids:
                source_weights[research_id] = source_weights.get(research_id, 0.0) + 1.0

            recommendations = ResearchService._get_qdrant_recommendations_from_source_ids(
                source_research_ids=source_ids,
                exclude_research_ids=source_ids,
                limit=limit,
                log_context=f"graph user_id={user_id}",
                source_weights=source_weights,
            )

        for rec in recommendations:
            score = float(rec.get("similarity_score", 0.0))
            if score < min_score:
                continue

            rec_id = rec.get("id")
            node = None
            if rec_id is not None:
                details = ResearchService._safe_get_research_details(db, rec_id, viewer_user_id=user_id)
                if details:
                    node = ResearchService._graph_node_from_research_details(details, node_type="recommended")

            if not node:
                node = ResearchService._graph_node_from_payload(
                    research_id=rec_id,
                    title=rec.get("title", "Unknown"),
                    user_id=rec.get("user_id"),
                    research_link=rec.get("research_link"),
                    node_type="recommended",
                )

            nodes_by_id.setdefault(node["id"], node)
            edges.append(
                {
                    "source": user_node["id"],
                    "target": node["id"],
                    "weight": round(score, 6),
                    "relation": "recommendation",
                }
            )

        return {
            "meta": {
                "user_id": user_id,
                "limit": limit,
                "min_score": min_score,
                "distance": "cosine",
                "embedding_model": settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
                "visit_count": len(visited_ids),
                "like_count": len(liked_ids),
                "source_count": len(source_ids),
            },
            "nodes": list(nodes_by_id.values()),
            "edges": edges,
        }

    @staticmethod
    def _get_qdrant_recommendations_from_source_ids(
        source_research_ids: set[int],
        exclude_research_ids: set[int],
        limit: int,
        log_context: str,
        source_weights: dict[int, float] | None = None,
    ) -> list[dict]:
        if not source_research_ids:
            return []

        # Cache key encodes exactly what determines the result. When the user adds
        # a new interaction the source IDs change → different key → natural miss.
        weights_key = frozenset(source_weights.items()) if source_weights else None
        cache_key = (
            frozenset(source_research_ids),
            frozenset(exclude_research_ids),
            limit,
            weights_key,
        )
        with _rec_lock:
            cached = _rec_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            centroid = qdrant_service.get_weighted_centroid(
                research_ids=list(source_research_ids),
                research_weights=source_weights,
            )
            if centroid is None:
                logger.warning("Could not compute centroid for %s", log_context)
                return []

            # Single query: fetch limit*10 chunk-level results (capped at 500) and
            # deduplicate by research_id client-side.
            chunk_limit = min(limit * 10, 500)
            search_results = qdrant_service.query_by_vector(
                vector=centroid,
                limit=chunk_limit,
                exclude_research_ids=exclude_research_ids,
            )

            # Keep the highest-score chunk per research_id, then take the top `limit`.
            best_per_research: dict[int, Any] = {}
            for point in search_results:
                rid = point.payload.get("research_id")
                if rid is None:
                    continue
                if rid not in best_per_research or point.score > best_per_research[rid].score:
                    best_per_research[rid] = point

            top_points = sorted(best_per_research.values(), key=lambda p: p.score, reverse=True)[:limit]

            result = [
                {
                    "id": p.payload.get("research_id"),
                    "title": str(p.payload.get("title", "Unknown")),
                    "user_id": p.payload.get("user_id"),
                    "research_link": p.payload.get("research_link"),
                    "vector_blob_name": p.payload.get("vector_link", ""),
                    "similarity_score": round(p.score, 6),
                }
                for p in top_points
            ]
            with _rec_lock:
                _rec_cache[cache_key] = result
            return result
        except Exception as e:
            logger.warning(
                "Error searching Qdrant for recommendations (%s): %s",
                log_context,
                e,
            )
            return []

    @staticmethod
    def create_research_with_pdf_immediate(
        db: Session,
        user_id: int,
        title: str,
        description: str | None,
        document_bytes: bytes,
        document_filename: str,
        document_content_type: str,
        author_ids: list[int] | None = None,
    ) -> dict:
        """Create research record immediately, queue embeddings for background processing."""
        try:
            # Validate user
            UsersRepository.get_by_id(db, user_id)

            # Validate PDF
            if document_content_type != "application/pdf":
                raise ValueError("Invalid document type. Only PDF is allowed")

            max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
            if len(document_bytes) > max_size:
                raise ValueError(f"PDF too large. Max {settings.MAX_UPLOAD_SIZE_MB}MB")

            # Extract text immediately to validate
            extracted_text = ResearchService._extract_pdf_text(document_bytes)
            if not extracted_text.strip():
                raise ValueError("No text could be extracted from the PDF")

            # Prepare blob names
            safe_title = ResearchService._sanitize_title(title)
            research_file_name = f"{safe_title}_research.pdf"
            subfolder = f"research/{user_id}/"

            # Upload research PDF immediately
            pdf_upload = blob_storage_service.upload_file(
                file_content=io.BytesIO(document_bytes),
                file_name=document_filename,
                container_type="documents",
                metadata={"type": "research", "user_id": str(user_id), "title": title},
                subfolder=subfolder,
                fixed_blob_name=research_file_name,
            )

            # Create research record with status=processing, vector_link=null
            research = ResearchRepository.create(
                db,
                user_id=user_id,
                title=title,
                description=description,
                research_link=pdf_upload["url"],
                vector_link="",  # will be updated by background task
            )
            # Set status to processing
            research.status = "processing"
            db.flush()

            # Add co-authors (skip invalid or duplicate ids silently)
            if author_ids:
                for uid in author_ids:
                    if uid == user_id:
                        continue
                    try:
                        UsersRepository.get_by_id(db, uid)
                    except ValueError:
                        continue
                    if not ResearchAuthorsRepository.get_by_research_and_user(db, research.id, uid):
                        ResearchAuthorsRepository.add(db, research.id, uid)

            db.commit()
            db.refresh(research)

            with _map_lock:
                _map_cache.clear()

            return {
                "success": True,
                "id": research.id,
                "research_link": research.research_link,
                "vector_link": None,
                "description": research.description,
                "status": research.status,
            }
        except ValueError:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise

    @staticmethod
    def process_research_embeddings_background(
        research_id: int,
        user_id: int,
        title: str,
        research_link: str,
        document_bytes: bytes,
    ) -> None:
        """Process embeddings in background and update research record."""
        db = SessionLocal()
        vector_blob_name = None
        try:
            research = ResearchRepository.get_by_id(db, research_id)
            if not research:
                logger.error(f"Research {research_id} not found for background processing")
                return

            # Extract text
            extracted_text = ResearchService._extract_pdf_text(document_bytes)
            if not extracted_text.strip():
                research.status = "failed"
                db.commit()
                logger.error(f"No text extracted for research {research_id}")
                return

            # Generate embeddings
            chunks = ResearchService._chunk_text(extracted_text)
            embeddings = ResearchService._generate_embeddings(chunks)

            # Prepare vector blob
            safe_title = ResearchService._sanitize_title(title)
            vector_file_name = f"{safe_title}_vector.json"
            subfolder = f"research/{user_id}/"
            
            vector_created_at = datetime.utcnow().isoformat()
            vector_payload = {
                "user_id": user_id,
                "title": title,
                "created_at": vector_created_at,
                "text_length": len(extracted_text),
                "embedding_model": settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
                "chunks": chunks,
                "embeddings": embeddings,
            }
            vector_bytes = json.dumps(vector_payload).encode("utf-8")

            # Upload vector blob
            vector_upload = blob_storage_service.upload_file(
                file_content=io.BytesIO(vector_bytes),
                file_name=vector_file_name,
                container_type="vectorized",
                metadata={"type": "research_vector", "user_id": str(user_id), "title": title},
                subfolder=subfolder,
                fixed_blob_name=vector_file_name,
            )
            vector_blob_name = vector_upload["blob_name"]

            # Sync to Qdrant
            ResearchService._sync_research_embeddings_to_qdrant(
                research_id=research_id,
                user_id=user_id,
                title=title,
                research_link=research_link,
                vector_link=vector_upload["url"],
                chunks=chunks,
                embeddings=embeddings,
                created_at=vector_created_at,
            )

            # Update research record
            research.vector_link = vector_upload["url"]
            research.status = "ready"
            db.commit()
            logger.info(f"Successfully processed embeddings for research {research_id}")

        except RateLimitError as e:
            db.rollback()
            research.status = "failed"
            db.commit()
            logger.error(f"Rate limit error processing research {research_id}: {e}")
            if vector_blob_name:
                try:
                    blob_storage_service.delete_file(
                        blob_name=vector_blob_name,
                        container_type="vectorized",
                    )
                except Exception:
                    pass
        except Exception as e:
            db.rollback()
            research.status = "failed"
            db.commit()
            logger.error(f"Error processing embeddings for research {research_id}: {e}")
            if vector_blob_name:
                try:
                    blob_storage_service.delete_file(
                        blob_name=vector_blob_name,
                        container_type="vectorized",
                    )
                except Exception:
                    pass
        finally:
            db.close()

    @staticmethod
    def create_research_with_pdf_sync(
        db: Session,
        user_id: int,
        title: str,
        description: str | None,
        document_bytes: bytes,
        document_filename: str,
        document_content_type: str,
    ) -> dict:
        """Versión síncrona para evitar conflictos async/sync con SQLAlchemy."""
        research_blob_name = None
        vector_blob_name = None
        try:
            # Validate user
            UsersRepository.get_by_id(db, user_id)

            # Validate PDF
            if document_content_type != "application/pdf":
                raise ValueError("Invalid document type. Only PDF is allowed")

            max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
            if len(document_bytes) > max_size:
                raise ValueError(f"PDF too large. Max {settings.MAX_UPLOAD_SIZE_MB}MB")

            # Extract text
            extracted_text = ResearchService._extract_pdf_text(document_bytes)
            if not extracted_text.strip():
                raise ValueError("No text could be extracted from the PDF")

            # Prepare blob names
            safe_title = ResearchService._sanitize_title(title)
            research_file_name = f"{safe_title}_research.pdf"
            vector_file_name = f"{safe_title}_vector.json"
            subfolder = f"research/{user_id}/"

            # Upload research PDF
            pdf_upload = blob_storage_service.upload_file(
                file_content=io.BytesIO(document_bytes),
                file_name=document_filename,
                container_type="documents",
                metadata={"type": "research", "user_id": str(user_id), "title": title},
                subfolder=subfolder,
                fixed_blob_name=research_file_name,
            )
            research_blob_name = pdf_upload["blob_name"]

            # Generate embeddings
            chunks = ResearchService._chunk_text(extracted_text)
            embeddings = ResearchService._generate_embeddings(chunks)

            vector_created_at = datetime.utcnow().isoformat()
            vector_payload = {
                "user_id": user_id,
                "title": title,
                "created_at": vector_created_at,
                "text_length": len(extracted_text),
                "embedding_model": settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
                "chunks": chunks,
                "embeddings": embeddings,
            }
            vector_bytes = json.dumps(vector_payload).encode("utf-8")

            vector_upload = blob_storage_service.upload_file(
                file_content=io.BytesIO(vector_bytes),
                file_name=vector_file_name,
                container_type="vectorized",
                metadata={"type": "research_vector", "user_id": str(user_id), "title": title},
                subfolder=subfolder,
                fixed_blob_name=vector_file_name,
            )
            vector_blob_name = vector_upload["blob_name"]

            # Persist research
            research = ResearchRepository.create(
                db,
                user_id=user_id,
                title=title,
                description=description,
                research_link=pdf_upload["url"],
                vector_link=vector_upload["url"],
            )

            ResearchService._sync_research_embeddings_to_qdrant(
                research_id=research.id,
                user_id=user_id,
                title=title,
                research_link=pdf_upload["url"],
                vector_link=vector_upload["url"],
                chunks=chunks,
                embeddings=embeddings,
                created_at=vector_created_at,
            )

            db.commit()
            db.refresh(research)

            return {
                "success": True,
                "id": research.id,
                "research_link": research.research_link,
                "vector_link": research.vector_link,
                "description": research.description,
            }
        except ValueError:
            db.rollback()
            raise
        except RateLimitError:
            db.rollback()
            if research_blob_name:
                try:
                    blob_storage_service.delete_file(
                        blob_name=research_blob_name,
                        container_type="documents",
                    )
                except Exception:
                    pass
            if vector_blob_name:
                try:
                    blob_storage_service.delete_file(
                        blob_name=vector_blob_name,
                        container_type="vectorized",
                    )
                except Exception:
                    pass
            raise
        except Exception as e:
            db.rollback()
            error_msg = str(e) if str(e) else repr(e)
            tb = traceback.format_exc()
            logger.error("Error creating research: %s\nTraceback: %s", error_msg, tb)
            # Cleanup blobs if created
            if research_blob_name:
                try:
                    blob_storage_service.delete_file(
                        blob_name=research_blob_name,
                        container_type="documents",
                    )
                except Exception:
                    pass
            if vector_blob_name:
                try:
                    blob_storage_service.delete_file(
                        blob_name=vector_blob_name,
                        container_type="vectorized",
                    )
                except Exception:
                    pass
            raise Exception(f"Error creating research: {error_msg}\nDetails: {tb}")

    @staticmethod
    async def create_research_with_pdf(
        db: Session,
        user_id: int,
        title: str,
        description: str | None,
        document: UploadFile,
    ) -> dict:
        research_blob_name = None
        vector_blob_name = None
        try:
            # Validate user
            UsersRepository.get_by_id(db, user_id)

            # Validate PDF
            if document.content_type != "application/pdf":
                raise ValueError("Invalid document type. Only PDF is allowed")

            max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
            pdf_bytes = await document.read()
            if len(pdf_bytes) > max_size:
                raise ValueError(f"PDF too large. Max {settings.MAX_UPLOAD_SIZE_MB}MB")

            # Extract text
            extracted_text = ResearchService._extract_pdf_text(pdf_bytes)
            if not extracted_text.strip():
                raise ValueError("No text could be extracted from the PDF")

            # Prepare blob names
            safe_title = ResearchService._sanitize_title(title)
            research_file_name = f"{safe_title}_research.pdf"
            vector_file_name = f"{safe_title}_vector.json"
            subfolder = f"research/{user_id}/"

            # Upload research PDF
            pdf_upload = blob_storage_service.upload_file(
                file_content=io.BytesIO(pdf_bytes),
                file_name=document.filename,
                container_type="documents",
                metadata={"type": "research", "user_id": str(user_id), "title": title},
                subfolder=subfolder,
                fixed_blob_name=research_file_name,
            )
            research_blob_name = pdf_upload["blob_name"]

            # Generate embeddings
            chunks = ResearchService._chunk_text(extracted_text)
            embeddings = ResearchService._generate_embeddings(chunks)

            vector_created_at = datetime.utcnow().isoformat()
            vector_payload = {
                "user_id": user_id,
                "title": title,
                "created_at": vector_created_at,
                "text_length": len(extracted_text),
                "embedding_model": settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
                "chunks": chunks,
                "embeddings": embeddings,
            }
            vector_bytes = json.dumps(vector_payload).encode("utf-8")

            vector_upload = blob_storage_service.upload_file(
                file_content=io.BytesIO(vector_bytes),
                file_name=vector_file_name,
                container_type="vectorized",
                metadata={"type": "research_vector", "user_id": str(user_id), "title": title},
                subfolder=subfolder,
                fixed_blob_name=vector_file_name,
            )
            vector_blob_name = vector_upload["blob_name"]

            # Persist research
            research = ResearchRepository.create(
                db,
                user_id=user_id,
                title=title,
                description=description,
                research_link=pdf_upload["url"],
                vector_link=vector_upload["url"],
            )

            ResearchService._sync_research_embeddings_to_qdrant(
                research_id=research.id,
                user_id=user_id,
                title=title,
                research_link=pdf_upload["url"],
                vector_link=vector_upload["url"],
                chunks=chunks,
                embeddings=embeddings,
                created_at=vector_created_at,
            )

            db.commit()
            db.refresh(research)

            return {
                "success": True,
                "id": research.id,
                "research_link": research.research_link,
                "vector_link": research.vector_link,
                "description": research.description,
            }
        except ValueError:
            db.rollback()
            raise
        except RateLimitError:
            db.rollback()
            if research_blob_name:
                try:
                    blob_storage_service.delete_file(
                        blob_name=research_blob_name,
                        container_type="documents",
                    )
                except Exception:
                    pass
            if vector_blob_name:
                try:
                    blob_storage_service.delete_file(
                        blob_name=vector_blob_name,
                        container_type="vectorized",
                    )
                except Exception:
                    pass
            raise
        except Exception as e:
            db.rollback()
            error_msg = str(e) if str(e) else repr(e)
            tb = traceback.format_exc()
            logger.error("Error creating research: %s\nTraceback: %s", error_msg, tb)
            # Cleanup blobs if created
            if research_blob_name:
                try:
                    blob_storage_service.delete_file(
                        blob_name=research_blob_name,
                        container_type="documents",
                    )
                except Exception:
                    pass
            if vector_blob_name:
                try:
                    blob_storage_service.delete_file(
                        blob_name=vector_blob_name,
                        container_type="vectorized",
                    )
                except Exception:
                    pass
            raise Exception(f"Error creating research: {error_msg}\nDetails: {tb}")

    @staticmethod
    def update_research(db: Session, research_id: int, updates: dict) -> dict:
        try:
            research = ResearchRepository.update(db, research_id, updates)
            db.commit()
            db.refresh(research)
            
            return {
                "success": True,
                "id": research.id,
                "title": research.title,
                "description": research.description,
                "research_link": research.research_link,
                "vector_link": research.vector_link,
            }
        except ValueError:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise

    @staticmethod
    def delete_research(db: Session, research_id: int) -> bool:
        research = ResearchRepository.get_by_id(db, research_id)

        if qdrant_service.is_enabled:
            qdrant_service.delete_research_embeddings(research_id)

        with _map_lock:
            _map_cache.clear()

        for link in (research.research_link, research.vector_link):
            blob_info = ResearchService._extract_blob_info(link)
            if not blob_info:
                continue
            container_type, blob_name = blob_info
            blob_storage_service.delete_file(blob_name=blob_name, container_type=container_type)

        return ResearchRepository.delete(db, research_id)

    @staticmethod
    def get_research_authors(db: Session, research_id: int) -> dict:
        ResearchRepository.get_by_id(db, research_id)
        rows = ResearchAuthorsRepository.get_by_research(db, research_id)
        authors = [
            {
                "user_id": row.user.id,
                "first_name": row.user.first_name,
                "last_name": row.user.last_name,
                "email": row.user.email,
            }
            for row in rows
        ]
        return {"research_id": research_id, "authors": authors}

    @staticmethod
    def add_research_authors(db: Session, research_id: int, user_ids: list[int]) -> dict:
        ResearchRepository.get_by_id(db, research_id)
        added, skipped, not_found = [], [], []
        for uid in user_ids:
            try:
                UsersRepository.get_by_id(db, uid)
            except ValueError:
                not_found.append(uid)
                continue
            existing = ResearchAuthorsRepository.get_by_research_and_user(db, research_id, uid)
            if existing:
                skipped.append(uid)
            else:
                ResearchAuthorsRepository.add(db, research_id, uid)
                added.append(uid)
        db.commit()
        return {"success": True, "research_id": research_id, "added": added, "skipped": skipped, "not_found": not_found}

    @staticmethod
    def remove_research_authors(db: Session, research_id: int, user_ids: list[int]) -> dict:
        ResearchRepository.get_by_id(db, research_id)
        removed, not_found = [], []
        for uid in user_ids:
            deleted = ResearchAuthorsRepository.remove(db, research_id, uid)
            if deleted:
                removed.append(uid)
            else:
                not_found.append(uid)
        db.commit()
        return {"success": True, "research_id": research_id, "removed": removed, "not_found": not_found}
