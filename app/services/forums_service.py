from sqlalchemy.orm import Session
from app.repositories.forums_repository import ForumsRepository
from app.repositories.users_repository import UsersRepository
from app.schemas.forums import ForumCreate, ForumUpdate
from app.models.forums import Forums

class ForumsService:
    @staticmethod
    def list_forums(db: Session, skip: int = 0, limit: int = 50) -> list[Forums]:
        return ForumsRepository.list(db, skip=skip, limit=limit)

    @staticmethod
    def get_forum(db: Session, forum_id: int) -> Forums | None:
        return ForumsRepository.get_by_user_id(db, forum_id)

    @staticmethod
    def create_forum(db: Session, payload: ForumCreate) -> Forums:
        existing = ForumsRepository.get_by_user_id(db, payload.user_id)
        if existing:
            raise ValueError("User already has a forum")

        return ForumsRepository.create(
            db,
            user_id=payload.user_id,
            user_profession=payload.user_profession,
            user_description=payload.user_description
        )

    @staticmethod
    def update_forum(db: Session, user_id: int, payload: ForumUpdate) -> Forums | None:
        return UsersRepository.update(
            db=db, 
            user_id=user_id, 
            email=None, 
            first_name=None,
            last_name=None,
            password=None,
            photo=payload.photo
            ) and ForumsRepository.update(
            db,
            forum_id=user_id,
            user_profession=payload.user_profession,
            user_description=payload.user_description,
            is_public=payload.is_public
        )
    
    @staticmethod
    def delete_forum(db: Session, user_id: int) -> bool:
        forum = ForumsRepository.get_by_user_id(db, user_id)
        if not forum:
            return False
        ForumsRepository.delete(db, forum.id)
        return True
