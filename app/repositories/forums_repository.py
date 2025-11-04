from sqlalchemy.orm import Session, joinedload
from app.models.forums import Forums

class ForumsRepository:
    @staticmethod
    def list(db: Session, skip: int = 0, limit: int = 100):
        return (
            db.query(Forums)
            .filter(Forums.is_public == True)  # Only return public forums
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_by_user_id(db: Session, user_id: int):
        return (
            db.query(Forums)
            .options(joinedload(Forums.user))
            .filter(Forums.user_id == user_id)
            .first()
        )

    @staticmethod
    def create(db: Session, user_id: int, user_profession: str | None, user_description: str | None):
        forum = Forums(
            user_id=user_id,
            user_profession=user_profession,
            user_description=user_description
        )
        db.add(forum)
        db.commit()
        db.refresh(forum)
        return True

    @staticmethod
    def update(
        db: Session,
        forum_id: int,
        user_profession: str | None,
        user_description: str | None,
        is_public: bool | None
    ):
        
        forum = db.query(Forums).filter(Forums.user_id == forum_id).first()
        if not forum:
            raise ValueError("Forum not found")
        
        if user_profession:
            forum.user_profession = user_profession
        if user_description:
            forum.user_description = user_description
        if is_public is not None:
            forum.is_public = is_public
        db.commit()
        db.refresh(forum)
        return True

    @staticmethod
    def delete(db: Session, forum_id: int):
        forum = db.query(Forums).filter(Forums.id == forum_id).first()
        if not forum:
            return False
        db.delete(forum)
        db.commit()
        return True