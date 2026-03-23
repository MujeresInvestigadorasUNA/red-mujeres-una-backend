from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.models.research_likes import ResearchLike


class ResearchLikesRepository:
    @staticmethod
    def get_by_user_and_research(db: Session, user_id: int, research_id: int):
        return (
            db.query(ResearchLike)
            .filter(
                ResearchLike.user_id == user_id,
                ResearchLike.research_id == research_id,
            )
            .first()
        )

    @staticmethod
    def like(db: Session, user_id: int, research_id: int):
        existing = ResearchLikesRepository.get_by_user_and_research(
            db,
            user_id=user_id,
            research_id=research_id,
        )
        if existing:
            was_active = bool(existing.is_active)
            existing.is_active = True
            existing.liked_at = datetime.utcnow()
            existing.updated_at = datetime.utcnow()
            db.flush()
            return existing, was_active

        like = ResearchLike(
            user_id=user_id,
            research_id=research_id,
            is_active=True,
            liked_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(like)
        db.flush()
        return like, False

    @staticmethod
    def unlike(db: Session, user_id: int, research_id: int):
        existing = ResearchLikesRepository.get_by_user_and_research(
            db,
            user_id=user_id,
            research_id=research_id,
        )
        if not existing:
            return None, False

        if not existing.is_active:
            return existing, False

        existing.is_active = False
        existing.updated_at = datetime.utcnow()
        db.flush()
        return existing, True

    @staticmethod
    def list_recent_active_by_user(db: Session, user_id: int, limit: int = 5):
        return (
            db.query(ResearchLike)
            .options(joinedload(ResearchLike.research))
            .filter(
                ResearchLike.user_id == user_id,
                ResearchLike.is_active == True,
            )
            .order_by(ResearchLike.liked_at.desc(), ResearchLike.id.desc())
            .limit(limit)
            .all()
        )
