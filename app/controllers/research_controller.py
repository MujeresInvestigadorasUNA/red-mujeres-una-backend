from fastapi import HTTPException, status, UploadFile
import logging
from openai import RateLimitError
from sqlalchemy.orm import Session
from app.services.research_service import ResearchService

logger = logging.getLogger(__name__)


class ResearchController:
    @staticmethod
    def list_research(db: Session, skip: int = 0, limit: int = 100):
        return ResearchService.list_research(db, skip=skip, limit=limit)

    @staticmethod
    def get_research(db: Session, research_id: int):
        try:
            return ResearchService.get_research(db, research_id)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def get_user_research(db: Session, user_id: int):
        return ResearchService.get_user_research(db, user_id)

    @staticmethod
    def get_related_research(db: Session, research_id: int, limit: int = 5):
        try:
            return ResearchService.get_related_research(db, research_id=research_id, limit=limit)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def register_research_visit(db: Session, user_id: int, research_id: int):
        try:
            return ResearchService.register_research_visit(db, user_id=user_id, research_id=research_id)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def get_recent_research_visits(db: Session, user_id: int, limit: int = 5):
        try:
            return ResearchService.get_recent_research_visits(db, user_id=user_id, limit=limit)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def get_related_research_from_recent_visits(db: Session, user_id: int, limit: int = 4):
        try:
            return ResearchService.get_related_research_from_recent_visits(db, user_id=user_id, limit=limit)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def like_research(db: Session, user_id: int, research_id: int):
        try:
            return ResearchService.like_research(db, user_id=user_id, research_id=research_id)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def unlike_research(db: Session, user_id: int, research_id: int):
        try:
            return ResearchService.unlike_research(db, user_id=user_id, research_id=research_id)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def get_recent_research_likes(db: Session, user_id: int, limit: int = 5):
        try:
            return ResearchService.get_recent_research_likes(db, user_id=user_id, limit=limit)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def get_research_like_history(db: Session, user_id: int, skip: int = 0, limit: int = 50):
        try:
            return ResearchService.get_research_like_history(db, user_id=user_id, skip=skip, limit=limit)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def get_related_research_from_recent_interactions(db: Session, user_id: int, limit: int = 4):
        try:
            return ResearchService.get_related_research_from_recent_interactions(db, user_id=user_id, limit=limit)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def create_research_sync(
        db: Session,
        user_id: int,
        title: str,
        description: str | None,
        document_bytes: bytes,
        document_filename: str,
        document_content_type: str,
    ):
        try:
            return ResearchService.create_research_with_pdf_sync(
                db=db,
                user_id=user_id,
                title=title,
                description=description,
                document_bytes=document_bytes,
                document_filename=document_filename,
                document_content_type=document_content_type,
            )
        except RateLimitError as e:
            retry_after = 60
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=str(e),
                headers={"Retry-After": str(retry_after)},
            )
        except ValueError as e:
            logger.warning(f"Validation error: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            error_detail = str(e) if str(e) else repr(e)
            logger.error(f"Error in create_research: {error_detail}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_detail,
            )

    @staticmethod
    def update_research(db: Session, research_id: int, research_update: dict):
        try:
            return ResearchService.update_research(db, research_id, research_update)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def create_research(
        db: Session,
        user_id: int,
        title: str,
        description: str | None,
        document: UploadFile,
    ):
        try:
            return await ResearchService.create_research_with_pdf(
                db=db,
                user_id=user_id,
                title=title,
                description=description,
                document=document,
            )
        except RateLimitError as e:
            retry_after = 60
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=str(e),
                headers={"Retry-After": str(retry_after)},
            )
        except ValueError as e:
            logger.warning(f"Validation error: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            error_detail = str(e) if str(e) else repr(e)
            logger.error(f"Error in create_research: {error_detail}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_detail,
            )

    @staticmethod
    def delete_research(db: Session, research_id: int):
        if not ResearchService.delete_research(db, research_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research not found")
        return {"status": "ok"}
