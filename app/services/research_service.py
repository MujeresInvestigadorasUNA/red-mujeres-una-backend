import io
import json
import logging
import re
from datetime import datetime
from typing import List

from fastapi import UploadFile
from openai import AzureOpenAI
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.research import Research
from app.repositories.research_repository import ResearchRepository
from app.repositories.users_repository import UsersRepository
from app.services.blob_storage_service import blob_storage_service

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
        reader = PdfReader(io.BytesIO(pdf_bytes))
        texts = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            texts.append(page_text)
        return "\n".join(texts)

    @staticmethod
    def _chunk_text(text: str, max_chars: int = 3000, overlap: int = 200) -> List[str]:
        if max_chars <= 0:
            return [text]
        if overlap >= max_chars:
            overlap = 0

        chunks = []
        start = 0
        text_len = len(text)
        while start < text_len:
            end = min(start + max_chars, text_len)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start = end - overlap
            if start < 0:
                start = 0
            if start >= text_len:
                break
        return chunks or [text]

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

            vector_payload = {
                "user_id": user_id,
                "title": title,
                "created_at": datetime.utcnow().isoformat(),
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
            logger.error("Error creating research: %s", str(e))
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
            raise Exception(f"Error creating research: {str(e)}")

    @staticmethod
    def delete_research(db: Session, research_id: int) -> bool:
        return ResearchRepository.delete(db, research_id)
