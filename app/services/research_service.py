import io
import json
import logging
import math
import re
import traceback
from datetime import datetime
from typing import List
from urllib.parse import unquote, urlparse

from fastapi import UploadFile
from openai import AzureOpenAI
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.research import Research
from app.repositories.research_repository import ResearchRepository
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
    def _sanitize_title(title: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", title.strip())
        safe = safe.strip("_")
        return safe or "research"

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
        response = client.embeddings.create(
            input=chunks,
            model=settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
        )
        return [item.embedding for item in response.data]

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
    def create_research_with_pdf_sync(
        db: Session,
        user_id: int,
        title: str,
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
            }
        except ValueError:
            db.rollback()
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
            }
        except ValueError:
            db.rollback()
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
    def delete_research(db: Session, research_id: int) -> bool:
        return ResearchRepository.delete(db, research_id)
