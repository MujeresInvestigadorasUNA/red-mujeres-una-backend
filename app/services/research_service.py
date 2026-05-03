import io
import json
import logging
import math
import re
import time
import traceback
from datetime import datetime
from typing import List
from urllib.parse import unquote, urlparse

from fastapi import UploadFile
from openai import AzureOpenAI, RateLimitError
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.research import Research
from app.repositories.research_like_events_repository import ResearchLikeEventsRepository
from app.repositories.research_likes_repository import ResearchLikesRepository
from app.repositories.research_repository import ResearchRepository
from app.repositories.research_visits_repository import ResearchVisitsRepository
from app.repositories.users_repository import UsersRepository
from app.services.blob_storage_service import blob_storage_service
from app.services.qdrant_service import qdrant_service

logger = logging.getLogger(__name__)


class ResearchService:
    @staticmethod
    def list_research(db: Session, skip: int = 0, limit: int = 50) -> list[Research]:
        return ResearchRepository.list(db, skip=skip, limit=limit)

    @staticmethod
    def get_research(db: Session, research_id: int) -> Research | None:
        return ResearchRepository.get_by_id(db, research_id)

    @staticmethod
    def get_user_research(db: Session, user_id: int) -> list[Research]:
        return ResearchRepository.get_by_user_id(db, user_id)

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
            removed = ResearchVisitsRepository.delete_older_than_limit(db, user_id=user_id, keep_limit=5)
            db.commit()

            return {
                "success": True,
                "user_id": user_id,
                "research_id": research_id,
                "visited_at": visit.visited_at,
                "removed_old_visits": removed,
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
    def _extract_blob_name_from_url(blob_url: str) -> str:
        parsed = urlparse(blob_url)
        path_parts = parsed.path.lstrip("/").split("/", 1)
        if len(path_parts) != 2:
            raise ValueError("Invalid vector blob URL")
        return unquote(path_parts[1])

    @staticmethod
    def _load_vector_payload(vector_url: str) -> dict:
        blob_name = ResearchService._extract_blob_name_from_url(vector_url)
        return ResearchService._load_vector_payload_from_blob_name(blob_name)

    @staticmethod
    def _load_vector_payload_from_blob_name(blob_name: str) -> dict:
        payload_bytes = blob_storage_service.download_file(
            blob_name=blob_name,
            container_type="vectorized",
        )
        return json.loads(payload_bytes.decode("utf-8"))

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
    def get_related_research(db: Session, research_id: int, limit: int = 5) -> list[dict]:
        source_research = ResearchRepository.get_by_id(db, research_id)
        source_blob_name = ResearchService._extract_blob_name_from_url(source_research.vector_link)
        source_payload = ResearchService._load_vector_payload(source_research.vector_link)
        source_embeddings = source_payload.get("embeddings", [])

        source_centroid = ResearchService._centroid_embedding(source_embeddings)
        if not source_centroid:
            return []

        db_research_map: dict[str, Research] = {}
        for db_research in ResearchRepository.list_all(db):
            try:
                db_blob_name = ResearchService._extract_blob_name_from_url(db_research.vector_link)
                db_research_map[db_blob_name] = db_research
            except Exception:
                continue

        vector_blobs = blob_storage_service.list_files(container_type="vectorized", prefix="research/")

        scored: list[dict] = []
        for blob_info in vector_blobs:
            candidate_blob_name = blob_info.get("name")
            if not candidate_blob_name or candidate_blob_name == source_blob_name:
                continue

            try:
                candidate_payload = ResearchService._load_vector_payload_from_blob_name(candidate_blob_name)
                candidate_centroid = ResearchService._centroid_embedding(candidate_payload.get("embeddings", []))
                score = ResearchService._cosine_similarity(source_centroid, candidate_centroid)
                if score <= 0:
                    continue

                mapped_research = db_research_map.get(candidate_blob_name)
                payload_title = candidate_payload.get("title")
                payload_user_id = candidate_payload.get("user_id")

                title = payload_title or (mapped_research.title if mapped_research else candidate_blob_name)
                user_id = payload_user_id if payload_user_id is not None else (mapped_research.user_id if mapped_research else None)
                research_link = mapped_research.research_link if mapped_research else None
                result_id = mapped_research.id if mapped_research else None

                scored.append(
                    {
                        "id": result_id,
                        "title": str(title),
                        "user_id": user_id,
                        "research_link": research_link,
                        "vector_blob_name": candidate_blob_name,
                        "similarity_score": round(score, 6),
                    }
                )
            except Exception as e:
                logger.warning(
                    "Skipping candidate blob=%s while computing similarity: %s",
                    candidate_blob_name,
                    e,
                )

        scored.sort(key=lambda item: item["similarity_score"], reverse=True)
        return scored[:limit]

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
    def get_related_research_from_recent_interactions(db: Session, user_id: int, limit: int = 5) -> list[dict]:
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

        return ResearchService._get_qdrant_recommendations_from_source_ids(
            source_research_ids=source_research_ids,
            exclude_research_ids=source_research_ids,
            limit=limit,
            log_context=f"interactions user_id={user_id}",
            source_weights=source_weights,
        )

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

        try:
            scored: list[dict] = []
            seen_ids = set()

            # Qdrant returns chunk-level points. Fetch in widening windows so we can
            # deduplicate by research_id and still return enough unique recommendations.
            candidate_limits = [max(20, limit * 5), max(100, limit * 25), max(300, limit * 60)]

            for qdrant_limit in candidate_limits:
                if len(scored) >= limit:
                    break

                search_results = qdrant_service.search_by_research_ids(
                    research_ids=list(source_research_ids),
                    limit=qdrant_limit,
                    exclude_research_ids=exclude_research_ids,
                    research_weights=source_weights,
                )

                for point in search_results:
                    if len(scored) >= limit:
                        break

                    payload = point.payload
                    research_id = payload.get("research_id")

                    # Skip duplicates (same research_id, different chunks)
                    if research_id in seen_ids:
                        continue
                    seen_ids.add(research_id)

                    title = payload.get("title", "Unknown")
                    user_id_from_payload = payload.get("user_id")
                    research_link = payload.get("research_link")

                    scored.append(
                        {
                            "id": research_id,
                            "title": str(title),
                            "user_id": user_id_from_payload,
                            "research_link": research_link,
                            "vector_blob_name": payload.get("vector_link", ""),
                            "similarity_score": round(point.score, 6),
                        }
                    )

            return scored
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
            db.commit()
            db.refresh(research)

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

        for link in (research.research_link, research.vector_link):
            blob_info = ResearchService._extract_blob_info(link)
            if not blob_info:
                continue
            container_type, blob_name = blob_info
            blob_storage_service.delete_file(blob_name=blob_name, container_type=container_type)

        return ResearchRepository.delete(db, research_id)
