from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from app.services.forums_service import ForumsService
from app.schemas.forums import ForumCreate, ForumUpdate

class ForumsController:
    @staticmethod
    def list_forums(db: Session, skip: int = 0, limit: int = 100):
        return ForumsService.list_forums(db, skip, limit)

    @staticmethod
    def get_forum(db: Session, forum_id: int):
        forum = ForumsService.get_forum(db, forum_id)
        if not forum:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forum not found")
        return forum

    @staticmethod
    def create_forum(db: Session, payload: ForumCreate):
        try:
            ForumsService.create_forum(db, payload)
            return {"success": True}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    def update_forum(db: Session, forum_id: int, payload: ForumUpdate):
        try:
            ForumsService.update_forum(db, forum_id, payload)
            return {"success": True}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    def delete_forum(db: Session, forum_id: int):
        if not ForumsService.delete_forum(db, forum_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forum not found")
        return {"status": "ok"}